#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Code generation module from DSL
Version 3.2 - Integration with two-stage pipeline
"""

import re
import json
import subprocess
import requests
from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import datetime

# Import quality-aware DSL structures
from uml_extract import (
    QualityAwareDSL,
    QualityMetrics,
    ValidationError,
    DSLValidator,
    ErrorType,
    ValidationLevel,
    generate_quality_aware_dsl,
    extract_uml_elements_with_quality,
    extract_raw_dsl_from_text,
    apply_validation_and_repair,
    validate_dsl_only,
    get_dsl_state
)

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================
# Code generation functions
# ===============================

def parse_dsl_to_uml_with_quality(dsl_text: str) -> QualityAwareDSL:
    """
    Parse DSL text and convert to QualityAwareDSL object.
    Supports multiple DSL formats.
    """
    dsl = QualityAwareDSL()
    
    # ============================================================
    # 1. Parse classes
    # ============================================================
    
    # Format 1: Class ClassName: Attributes: attr1, attr2 Methods: method1, method2
    class_pattern1 = r'Class\s+(\w+):\s*(?:Attributes:\s*([^\n]*))?\s*(?:Methods:\s*([^\n]*))?'
    
    # Format 2: Class ClassName: (multi-line)
    class_pattern2 = r'Class\s+(\w+):\s*\n\s*Attributes:\s*([^\n]*)\s*\n\s*Methods:\s*([^\n]*)'
    
    class_matches = list(re.finditer(class_pattern2, dsl_text, re.IGNORECASE | re.MULTILINE))
    
    if not class_matches:
        class_matches = list(re.finditer(class_pattern1, dsl_text, re.IGNORECASE | re.MULTILINE | re.DOTALL))
    
    for match in class_matches:
        class_name = match.group(1).strip()
        
        if len(match.groups()) >= 3:
            attributes_str = match.group(2).strip() if match.group(2) else ""
            methods_str = match.group(3).strip() if match.group(3) else ""
        else:
            attributes_str = ""
            methods_str = ""
        
        attributes = []
        if attributes_str and attributes_str not in ['(none)', 'None', '']:
            attributes_str = attributes_str.strip('[]')
            attrs = re.split(r'[,;]\s*', attributes_str)
            for attr in attrs:
                attr_clean = attr.strip().strip('"\'')
                if attr_clean and attr_clean not in ['(none)', 'None', '']:
                    attributes.append(attr_clean)
        
        methods = []
        if methods_str and methods_str not in ['(none)', 'None', '']:
            methods_str = methods_str.strip('[]')
            mths = re.split(r'[,;]\s*', methods_str)
            for mth in mths:
                mth_clean = mth.strip().strip('"\'')
                if mth_clean and mth_clean not in ['(none)', 'None', '']:
                    mth_clean = mth_clean.replace('()', '').strip()
                    if mth_clean:
                        methods.append(mth_clean)
        
        if class_name:
            dsl.add_class(class_name, attributes, methods)
            logger.info(f"Parsed class: {class_name}")
    
    # Fallback: more flexible parsing
    if not dsl.classes:
        lines = dsl_text.split('\n')
        current_class = None
        current_attrs = []
        current_methods = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            class_match = re.match(r'^(?:Class|class)\s+(\w+)', line)
            if class_match:
                if current_class:
                    dsl.add_class(current_class, current_attrs, current_methods)
                current_class = class_match.group(1)
                current_attrs = []
                current_methods = []
                continue
            
            if current_class and re.match(r'^\s*Attributes:', line, re.IGNORECASE):
                attrs_str = re.sub(r'^\s*Attributes:\s*', '', line, flags=re.IGNORECASE)
                if attrs_str and attrs_str not in ['(none)', 'None', '']:
                    attrs_str = attrs_str.strip('[]')
                    for attr in re.split(r'[,;]\s*', attrs_str):
                        attr_clean = attr.strip().strip('"\'')
                        if attr_clean and attr_clean not in ['(none)', 'None', '']:
                            current_attrs.append(attr_clean)
                continue
            
            if current_class and re.match(r'^\s*Methods:', line, re.IGNORECASE):
                methods_str = re.sub(r'^\s*Methods:\s*', '', line, flags=re.IGNORECASE)
                if methods_str and methods_str not in ['(none)', 'None', '']:
                    methods_str = methods_str.strip('[]')
                    for mth in re.split(r'[,;]\s*', methods_str):
                        mth_clean = mth.strip().strip('"\'')
                        if mth_clean and mth_clean not in ['(none)', 'None', '']:
                            mth_clean = mth_clean.replace('()', '').strip()
                            if mth_clean:
                                current_methods.append(mth_clean)
                continue
            
            if current_class and ':' in line and '()' not in line:
                attr_clean = line.strip().strip('- ').strip('"\'')
                if attr_clean and attr_clean not in ['(none)', 'None', '']:
                    current_attrs.append(attr_clean)
        
        if current_class:
            dsl.add_class(current_class, current_attrs, current_methods)
    
    # ============================================================
    # 2. Parse relations
    # ============================================================
    
    relation_pattern1 = r'Relation:\s*(\w+)\s+(\w+)\s+(\w+)'
    relation_pattern2 = r'(\w+)\s*->\s*(\w+)\s*(?:\((\w+)\))?'
    relation_pattern3 = r'(\w+)\s+(association|aggregation|composition|inheritance|dependency)\s+(\w+)'
    
    relation_matches = list(re.finditer(relation_pattern1, dsl_text, re.IGNORECASE))
    
    if not relation_matches:
        relation_matches = list(re.finditer(relation_pattern2, dsl_text, re.IGNORECASE))
    
    if not relation_matches:
        relation_matches = list(re.finditer(relation_pattern3, dsl_text, re.IGNORECASE))
    
    valid_types = ['association', 'aggregation', 'composition', 'inheritance', 'dependency']
    
    for match in relation_matches:
        if len(match.groups()) == 3:
            source = match.group(1).strip()
            possible_type = match.group(2).lower().strip()
            third = match.group(3).strip()
            
            if possible_type in valid_types:
                rel_type = possible_type
                target = third
            else:
                target = possible_type
                rel_type = third.lower() if third.lower() in valid_types else 'association'
        else:
            source = match.group(1).strip()
            target = match.group(2).strip()
            rel_type = match.group(3).lower().strip() if match.group(3) else 'association'
        
        if rel_type not in valid_types:
            type_map = {'extends': 'inheritance', 'implements': 'inheritance', 
                       'has': 'composition', 'contains': 'composition',
                       'uses': 'dependency', 'depends': 'dependency'}
            rel_type = type_map.get(rel_type, 'association')
        
        if source in dsl.classes and target in dsl.classes:
            dsl.add_relation(source, target, rel_type)
        else:
            dsl.add_relation(source, target, rel_type)
    
    # ============================================================
    # 3. Validation
    # ============================================================
    
    validator = DSLValidator()
    errors = validator.validate(dsl)
    dsl.validation_errors = errors
    dsl.metadata['total_errors'] = len(errors)
    
    logger.info(f"Parsing complete: {len(dsl.classes)} classes, {len(dsl.relations)} relations, {len(errors)} errors")
    return dsl

def is_ollama_available() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def get_available_models() -> List[str]:
    """Get list of available models from Ollama."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [model['name'] for model in data.get('models', [])]
            code_models = [m for m in models if any(keyword in m.lower() for keyword in 
                        ['code', 'coder', 'llama', 'mistral', 'phi', 'gemma', 'deepseek', 'neural'])]
            return code_models if code_models else models
        return []
    except:
        return []

def generate_code_with_fallback(dsl_text: str, language: str, use_llm: bool = True, 
                                model: str = "gemma:2b") -> Tuple[str, bool]:
    """
    Generate code from DSL using LLM or local fallback.
    Returns (code, used_llm).
    """
    if use_llm and is_ollama_available():
        try:
            code = generate_code_with_llm(dsl_text, language, model)
            if code and len(code) > 50:
                return code, True
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
    
    return generate_code_locally(dsl_text, language), False

def generate_code_with_llm(dsl_text: str, language: str, model: str = "gemma:2b") -> str:
    """Generate code using Ollama LLM."""
    prompt = f"""You are an expert software engineer. Generate {language} code from this UML DSL description.

DSL:
{dsl_text}

Requirements:
1. Generate complete, working {language} code
2. Include all classes, attributes, and methods
3. Implement all relationships (inheritance, composition, aggregation, association)
4. Add proper imports and package declarations
5. Include constructors, getters, setters
6. Follow {language} coding conventions and best practices
7. Add comments to explain the code
8. Ensure the code is syntactically correct and compiles

Return only the {language} code without any explanations or markdown formatting.
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,
                "max_tokens": 2000
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            code = result.get('response', '').strip()
            code = re.sub(r'```\w*\n?', '', code)
            code = re.sub(r'```\n?', '', code)
            return code
        else:
            raise Exception(f"Ollama API error: {response.status_code}")
    except Exception as e:
        logger.error(f"LLM generation error: {e}")
        raise

def generate_code_locally(dsl_text: str, language: str) -> str:
    """Generate code locally without LLM (Python only)."""
    if language.lower() != "python":
        return f"# Local generation only supports Python.\n# Please use LLM for {language} generation.\n\n{dsl_text}"
    
    dsl = parse_dsl_to_uml_with_quality(dsl_text)
    
    if not dsl.classes:
        return "# No classes found in DSL"
    
    lines = []
    
    lines.append('"""')
    lines.append('Generated UML Code')
    lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'Classes: {len(dsl.classes)}')
    lines.append(f'Relations: {len(dsl.relations)}')
    if hasattr(dsl, 'get_reliability_score'):
        lines.append(f'Reliability: {dsl.get_reliability_score():.3f}')
    lines.append('"""')
    lines.append('')
    lines.append('from typing import List, Optional')
    lines.append('')
    
    for class_name, class_data in dsl.classes.items():
        confidence = class_data.get('confidence', 0.95)
        lines.append(f'class {class_name}:')
        lines.append(f'    """Represents a {class_name} in the system. (Confidence: {confidence:.3f})"""')
        lines.append('')
        
        lines.append(f'    def __init__(self,')
        params = []
        init_body = []
        
        attributes = class_data.get('attributes', [])
        if attributes:
            lines.append('        """Initialize the class with attributes."""')
            for attr in attributes:
                attr_name = attr.replace(' ', '_').lower()
                params.append(f'{attr_name}: Optional[str] = None')
                init_body.append(f'        self.{attr_name} = {attr_name}')
        
        for relation in dsl.relations:
            if relation['type'] in ['composition', 'aggregation'] and relation['source'] == class_name:
                target = relation['target'].lower()
                params.append(f'{target}: Optional["{relation["target"]}"] = None')
                init_body.append(f'        self.{target} = {target}')
        
        if params:
            lines.append('        ' + ',\n        '.join(params) + ')')
            for line in init_body:
                lines.append(line)
            lines.append('')
        else:
            lines.append('        pass')
            lines.append('')
        
        methods = class_data.get('methods', [])
        if methods:
            lines.append('    # Methods')
            for method in methods:
                method_name = method.replace(' ', '_').lower()
                lines.append(f'    def {method_name}(self):')
                lines.append(f'        """Execute the {method} operation."""')
                lines.append('        pass')
                lines.append('')
    
    inheritance_relations = [r for r in dsl.relations if r['type'] == 'inheritance']
    for relation in inheritance_relations:
        child = relation['source']
        parent = relation['target']
        lines.append(f'# Note: {child} inherits from {parent}')
    
    if dsl.classes:
        lines.append('')
        lines.append('# Example usage')
        lines.append('if __name__ == "__main__":')
        first_class = list(dsl.classes.keys())[0]
        lines.append(f'    obj = {first_class}()')
        lines.append(f'    print(f"Created {{obj}}")')
    
    return '\n'.join(lines)

def generate_dsl(text: str) -> str:
    """Generate DSL from text (compatibility function)."""
    dsl = extract_uml_elements_with_quality(text, auto_repair=True)
    return generate_quality_aware_dsl(dsl)

def generate_dsl_text_from_object(dsl: QualityAwareDSL) -> str:
    """
    Generate a text representation of the DSL from the object.
    """
    return generate_quality_aware_dsl(dsl)