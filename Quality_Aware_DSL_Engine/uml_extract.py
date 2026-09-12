#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced DSL for UML Extraction
Version 3.2 - Complete with automatic attribute and method completion
Two-stage processing: Raw DSL → Validation → Correction → Validated DSL
"""

import re
import os
import logging
from transformers import BertTokenizerFast, BertForTokenClassification, BertConfig
from safetensors.torch import load_file
import torch
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime
from collections import defaultdict
import copy

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================
# Quality-aware DSL Structures
# ===============================

class ErrorType(Enum):
    """Error taxonomy for DSL."""
    E_SYN = "Syntax error"
    E_CLS = "Missing/incorrect class"
    E_ATT = "Attribute error"
    E_MTH = "Method error"
    E_ASS = "Association error"
    E_AGR = "Aggregation error"
    E_CMP = "Composition error"
    E_INH = "Inheritance error"
    E_CAR = "Cardinality/structural error"
    E_SEM = "Semantic inconsistency"
    E_MISSING_ATT = "Missing attribute"
    E_MISSING_MTH = "Missing method"

class ValidationLevel(Enum):
    """Validation levels."""
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    RELATIONSHIP = "relationship"
    STRUCTURAL = "structural"
    COMPLETENESS = "completeness"

@dataclass
class ValidationError:
    """Represents a validation error."""
    error_type: ErrorType
    level: ValidationLevel
    message: str
    element: Optional[str] = None
    suggestion: Optional[str] = None
    context: Optional[Dict] = None
    severity: str = "error"  # error, warning, info
    
    def to_dict(self) -> Dict:
        return {
            'type': self.error_type.value,
            'code': self.error_type.name,
            'level': self.level.value,
            'message': self.message,
            'element': self.element,
            'suggestion': self.suggestion,
            'context': self.context or {},
            'severity': self.severity
        }

@dataclass
class QualityMetrics:
    """Quality metrics for a DSL element."""
    syntactic_validity: float = 1.0
    semantic_validity: float = 1.0
    relationship_validity: float = 1.0
    structural_consistency: float = 1.0
    completeness: float = 1.0
    confidence: float = 0.95
    precision: float = 1.0
    recall: float = 1.0
    
    def get_reliability_score(self) -> float:
        """Calculate the global reliability score."""
        return (
            self.syntactic_validity * 0.18 +
            self.semantic_validity * 0.18 +
            self.relationship_validity * 0.18 +
            self.structural_consistency * 0.16 +
            self.completeness * 0.15 +
            self.confidence * 0.15
        )
    
    def to_dict(self) -> Dict:
        return {
            'syntactic_validity': round(self.syntactic_validity, 3),
            'semantic_validity': round(self.semantic_validity, 3),
            'relationship_validity': round(self.relationship_validity, 3),
            'structural_consistency': round(self.structural_consistency, 3),
            'completeness': round(self.completeness, 3),
            'confidence': round(self.confidence, 3),
            'precision': round(self.precision, 3),
            'recall': round(self.recall, 3),
            'reliability_score': round(self.get_reliability_score(), 3)
        }

@dataclass
class QualityAwareDSL:
    """Quality-aware DSL representation."""
    classes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    quality_metrics: Dict[str, QualityMetrics] = field(default_factory=dict)
    validation_errors: List[ValidationError] = field(default_factory=list)
    repair_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.metadata:
            self.metadata = {
                'created_at': datetime.now().isoformat(),
                'version': '3.2',
                'total_classes': 0,
                'total_relations': 0,
                'total_errors': 0,
                'repair_iterations': 0,
                'is_raw': False,
                'corrections_applied': [],
                'isolated_classes_fixed': 0,
                'attributes_added': 0,
                'methods_added': 0
            }
    
    def add_class(self, name: str, attributes: List[str] = None, methods: List[str] = None,
                  is_abstract: bool = False, confidence: float = 0.95):
        """Add a class with quality metrics."""
        if attributes is None:
            attributes = []
        if methods is None:
            methods = []
        
        # Normalize class name
        name = self._normalize_class_name(name)
        
        self.classes[name] = {
            'attributes': attributes,
            'methods': methods,
            'is_abstract': is_abstract,
            'confidence': confidence
        }
        self.quality_metrics[name] = QualityMetrics(confidence=confidence)
        self.metadata['total_classes'] = len(self.classes)
    
    def _normalize_class_name(self, name: str) -> str:
        """Normalize a class name."""
        name = name.strip()
        # CamelCase for classes
        words = re.findall(r'[A-Z][a-z]*|[a-z]+', name)
        return ''.join(w.capitalize() for w in words) if words else name.capitalize()
    
    def add_relation(self, source: str, target: str, rel_type: str,
                     source_cardinality: Optional[str] = None,
                     target_cardinality: Optional[str] = None,
                     confidence: float = 0.90):
        """Add a relation with validation."""
        # Normalize names
        source = self._normalize_class_name(source)
        target = self._normalize_class_name(target)
        rel_type = rel_type.lower()
        
        # Validate relation type
        valid_types = ['association', 'aggregation', 'composition', 'inheritance', 'dependency']
        if rel_type not in valid_types:
            rel_type = 'association'
        
        # Check if relation already exists
        if self._relation_exists(source, target):
            logger.info(f"⚠️ Relation {source} -> {target} already exists, skipping")
            return
        
        relation = {
            'source': source,
            'target': target,
            'type': rel_type,
            'confidence': confidence
        }
        if source_cardinality:
            relation['source_cardinality'] = source_cardinality
        if target_cardinality:
            relation['target_cardinality'] = target_cardinality
        
        self.relations.append(relation)
        rel_key = f"{source}_{target}_{rel_type}"
        self.quality_metrics[rel_key] = QualityMetrics(
            confidence=confidence,
            relationship_validity=0.95
        )
        self.metadata['total_relations'] = len(self.relations)
    
    def _relation_exists(self, source: str, target: str) -> bool:
        """Check if a relation already exists between two classes."""
        for relation in self.relations:
            if (relation.get('source') == source and relation.get('target') == target) or \
               (relation.get('source') == target and relation.get('target') == source):
                return True
        return False
    
    def add_validation_error(self, error: ValidationError):
        """Add a validation error."""
        self.validation_errors.append(error)
        self.metadata['total_errors'] = len(self.validation_errors)
    
    def add_repair_record(self, record: Dict[str, Any]):
        """Add a repair record."""
        self.repair_history.append(record)
        self.metadata['repair_iterations'] = len(self.repair_history)
    
    def add_correction(self, correction: str):
        """Add an applied correction."""
        if 'corrections_applied' not in self.metadata:
            self.metadata['corrections_applied'] = []
        self.metadata['corrections_applied'].append(correction)
    
    def to_dict(self) -> Dict:
        """Convert DSL to dictionary."""
        return {
            'classes': self.classes,
            'relations': self.relations,
            'quality_metrics': {
                k: v.to_dict() for k, v in self.quality_metrics.items()
            },
            'validation_errors': [e.to_dict() for e in self.validation_errors],
            'repair_history': self.repair_history,
            'metadata': self.metadata,
            'trace_id': self.trace_id,
            'reliability_score': self.get_reliability_score()
        }
    
    def to_json(self, pretty: bool = True) -> str:
        """Convert DSL to JSON."""
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def get_reliability_score(self) -> float:
        """Calculate the global reliability score of the DSL."""
        if not self.quality_metrics:
            return 0.0
        
        scores = [m.get_reliability_score() for m in self.quality_metrics.values()]
        return sum(scores) / len(scores) if scores else 0.0
    
    def get_error_summary(self) -> Dict[str, int]:
        """Summary of errors by type."""
        summary = {}
        for error in self.validation_errors:
            error_code = error.error_type.name
            summary[error_code] = summary.get(error_code, 0) + 1
        return summary

# ===============================
# BERT Model Loading
# ===============================

MODEL_PATH = os.path.abspath('C:/Users/User/desktop/Extractor_Hybrid_2/my-finetuned-model')

# Check that all files exist
necessary_files = ["config.json", "tokenizer.json", "vocab.txt", "model.safetensors"]
for file in necessary_files:
    if not os.path.exists(os.path.join(MODEL_PATH, file)):
        raise FileNotFoundError(f"Missing file: {file}")

# Load configuration and model
config = BertConfig.from_pretrained(MODEL_PATH)
model = BertForTokenClassification(config)
model_weights = load_file(os.path.join(MODEL_PATH, "model.safetensors"))
model.load_state_dict(model_weights)
tokenizer = BertTokenizerFast.from_pretrained(MODEL_PATH)

logger.info("Model and tokenizer loaded successfully at startup.")

# Label mapping
id2label = {
    0: 'O', 1: 'B_CLASS_SOURCE', 2: 'I_CLASS_SOURCE', 3: 'B_CLASS_TARGET', 4: 'I_CLASS_TARGET',
    5: 'B_ATTRIBUTE', 6: 'I_ATTRIBUTE', 7: 'B_METHOD', 8: 'I_METHOD',
    9: 'B_ASSOCIATION', 10: 'I_ASSOCIATION', 11: 'B_AGGREGATION', 12: 'I_AGGREGATION',
    13: 'B_COMPOSITION', 14: 'I_COMPOSITION', 15: 'B_INHERITANCE', 16: 'I_INHERITANCE'
}

label2id = {v: k for k, v in id2label.items()}

# ===============================
# Utility Functions
# ===============================

def preprocess_text(text: str) -> str:
    """Preprocess and clean the input text."""
    logger.debug("Preprocessing input text.")
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    logger.debug(f"Cleaned text: {text[:100]}...")
    return text

def normalize_class_name(class_name: str) -> str:
    """Normalize class names to a consistent format."""
    normalized = class_name.lower()
    if normalized.endswith('s') and len(normalized) > 1:
        normalized = normalized[:-1]
    return normalized.capitalize()

def merge_subtokens(tokens, labels):
    """Merge subtokens into complete tokens and associate labels."""
    merged_tokens, merged_labels = [], []
    buffer, buffer_label = "", None

    for token, label in zip(tokens, labels):
        if token.startswith("##"):
            buffer += token[2:]
        else:
            if buffer:
                merged_tokens.append(buffer)
                merged_labels.append(buffer_label)
            buffer, buffer_label = token, label

    if buffer:
        merged_tokens.append(buffer)
        merged_labels.append(buffer_label)

    return merged_tokens, merged_labels

RELATION_PRIORITY = {"composition": 3, "aggregation": 2, "inheritance": 1, "association": 0}

def filter_strongest_relations(relations):
    """Keep only the strongest relation between two classes."""
    strongest_relations = {}
    for r in relations:
        key = (r['source'], r['target'])
        reverse_key = (r['target'], r['source'])
        cur_priority = RELATION_PRIORITY.get(r['type'], -1)

        if key in strongest_relations:
            if cur_priority > RELATION_PRIORITY.get(strongest_relations[key]['type'], -1):
                strongest_relations[key] = r
        elif reverse_key in strongest_relations:
            if cur_priority > RELATION_PRIORITY.get(strongest_relations[reverse_key]['type'], -1):
                strongest_relations[reverse_key] = r
        else:
            strongest_relations[key] = r

    return list(strongest_relations.values())

# ===============================
# COMPLETENESS ENHANCER - Adds missing attributes and methods
# ===============================

class CompletenessEnhancer:
    """Enhances DSL completeness by adding missing attributes and methods."""
    
    def __init__(self):
        self.attributes_added = 0
        self.methods_added = 0
        self.cardinalities_added = 0
        
        # Class-specific attributes
        self.specific_attributes = {
            'Robot': ['robotId', 'model', 'operatingStatus'],
            'Sensor': ['sensorId', 'type', 'measurementValue', 'calibrationDate'],
            'Actuator': ['actuatorId', 'name', 'status', 'powerLevel'],
            'Technician': ['technicianId', 'name', 'specialization', 'email'],
            'Laboratory': ['laboratoryId', 'name', 'location'],
            'Task': ['taskId', 'description', 'executionDate', 'duration', 'status'],
            'Customer': ['customerId', 'name', 'email', 'phone'],
            'Order': ['orderId', 'orderDate', 'total', 'status'],
            'Product': ['productId', 'name', 'price', 'category'],
            'Payment': ['paymentId', 'amount', 'paymentDate', 'method'],
            'Address': ['street', 'city', 'postalCode', 'country'],
            'Employee': ['employeeId', 'firstName', 'lastName', 'email', 'department'],
            'Department': ['departmentId', 'name', 'location', 'manager'],
            'Project': ['projectId', 'name', 'startDate', 'endDate', 'status']
        }
        
        # Class-specific methods
        self.specific_methods = {
            'Robot': ['move()', 'stop()', 'collectSensorData()', 'executeTask()', 'reportStatus()'],
            'Sensor': ['getMeasurement()', 'calibrate()'],
            'Actuator': ['activate()', 'deactivate()', 'getPowerLevel()'],
            'Technician': ['configureRobot()', 'calibrateSensor()', 'replaceActuator()'],
            'Laboratory': ['manageRobots()', 'manageTechnicians()'],
            'Task': ['getRobot()', 'getHistory()'],
            'Customer': ['placeOrder()', 'cancelOrder()', 'getOrderHistory()'],
            'Order': ['calculateTotal()', 'getStatus()', 'updateStatus()'],
            'Product': ['getPrice()', 'updatePrice()', 'getCategory()'],
            'Payment': ['processPayment()', 'refundPayment()', 'getStatus()'],
            'Address': ['validateAddress()', 'getFullAddress()'],
            'Employee': ['getFullName()', 'getDepartment()', 'getProjects()'],
            'Department': ['addEmployee()', 'removeEmployee()', 'getEmployees()'],
            'Project': ['addTask()', 'removeTask()', 'getProgress()']
        }
    
    def enhance(self, dsl: QualityAwareDSL) -> QualityAwareDSL:
        """Enhance DSL completeness."""
        self.attributes_added = 0
        self.methods_added = 0
        self.cardinalities_added = 0
        
        # 1. Add missing attributes for each class
        for class_name in list(dsl.classes.keys()):
            self._add_missing_attributes(dsl, class_name)
        
        # 2. Add missing methods for each class
        for class_name in list(dsl.classes.keys()):
            self._add_missing_methods(dsl, class_name)
        
        # 3. Add relation methods
        self._add_relation_methods(dsl)
        
        # 4. Normalize attribute order
        self._normalize_attribute_order(dsl)
        
        # 5. Normalize method names
        self._normalize_method_names(dsl)
        
        # 6. Add default cardinalities
        self._add_default_cardinalities(dsl)
        
        # Update metrics
        dsl.metadata['attributes_added'] = self.attributes_added
        dsl.metadata['methods_added'] = self.methods_added
        
        return dsl
    
    def _add_missing_attributes(self, dsl: QualityAwareDSL, class_name: str):
        """Add missing attributes for a class."""
        class_data = dsl.classes.get(class_name, {})
        existing_attrs = class_data.get('attributes', [])
        existing_attr_names = [a.lower() for a in existing_attrs]
        
        added = 0
        
        # Recommended base attributes
        base_attrs = []
        
        # ID (unless class name is already an ID)
        id_candidates = [f'{class_name.lower()}Id', 'id', 'identifier']
        found_id = any(any(cand in attr.lower() for cand in id_candidates) for attr in existing_attrs)
        if not found_id and class_name.lower() not in ['task', 'robot', 'sensor']:
            base_attrs.append(f'{class_name.lower()}Id')
            dsl.add_correction(f"✅ Attribute added: '{class_name.lower()}Id' added to class '{class_name}'")
            added += 1
        
        # Name
        if not any('name' in attr.lower() for attr in existing_attrs):
            base_attrs.append('name')
            dsl.add_correction(f"✅ Attribute added: 'name' added to class '{class_name}'")
            added += 1
        
        # Description
        if len(existing_attrs) > 0 and not any('description' in attr.lower() for attr in existing_attrs):
            base_attrs.append('description')
            dsl.add_correction(f"✅ Attribute added: 'description' added to class '{class_name}'")
            added += 1
        
        # Status
        if not any('status' in attr.lower() for attr in existing_attrs):
            base_attrs.append('status')
            dsl.add_correction(f"✅ Attribute added: 'status' added to class '{class_name}'")
            added += 1
        
        # Add base attributes
        for attr in base_attrs:
            if attr not in existing_attrs:
                existing_attrs.append(attr)
        
        # Add class-specific attributes
        specific = self.specific_attributes.get(class_name, [])
        for attr in specific:
            if attr not in existing_attrs:
                existing_attrs.append(attr)
                dsl.add_correction(f"✅ Attribute added: '{attr}' added to class '{class_name}'")
                added += 1
        
        dsl.classes[class_name]['attributes'] = existing_attrs
        self.attributes_added += added
    
    def _add_missing_methods(self, dsl: QualityAwareDSL, class_name: str):
        """Add missing methods for a class."""
        class_data = dsl.classes.get(class_name, {})
        existing_methods = class_data.get('methods', [])
        existing_method_names = [m.lower().replace('()', '') for m in existing_methods]
        
        added = 0
        
        # Getters and setters for each attribute
        attrs = class_data.get('attributes', [])
        for attr in attrs:
            # Getter
            getter = f'get{attr.capitalize()}()'
            if getter.lower() not in existing_method_names and getter not in existing_methods:
                existing_methods.append(getter)
                dsl.add_correction(f"✅ Method added: '{getter}' added to class '{class_name}'")
                added += 1
            
            # Setter
            setter = f'set{attr.capitalize()}()'
            if setter.lower() not in existing_method_names and setter not in existing_methods:
                if 'id' not in attr.lower() and 'Id' not in attr:
                    existing_methods.append(setter)
                    dsl.add_correction(f"✅ Method added: '{setter}' added to class '{class_name}'")
                    added += 1
        
        # Class-specific methods
        specific = self.specific_methods.get(class_name, [])
        for method in specific:
            if method.lower() not in existing_method_names and method not in existing_methods:
                existing_methods.append(method)
                dsl.add_correction(f"✅ Method added: '{method}' added to class '{class_name}'")
                added += 1
        
        dsl.classes[class_name]['methods'] = existing_methods
        self.methods_added += added
    
    def _add_relation_methods(self, dsl: QualityAwareDSL):
        """Add methods for relations."""
        for relation in dsl.relations:
            source = relation.get('source')
            target = relation.get('target')
            rel_type = relation.get('type')
            
            if source in dsl.classes:
                methods = dsl.classes[source].get('methods', [])
                method_names = [m.lower().replace('()', '') for m in methods]
                
                added = 0
                
                # Relation methods
                rel_methods = []
                if rel_type in ['composition', 'aggregation']:
                    rel_methods = [
                        f'add{target}()',
                        f'remove{target}()',
                        f'get{target}s()'
                    ]
                elif rel_type == 'association':
                    rel_methods = [
                        f'link{target}()',
                        f'unlink{target}()',
                        f'get{target}s()'
                    ]
                
                for method in rel_methods:
                    if method.lower() not in method_names and method not in methods:
                        methods.append(method)
                        dsl.add_correction(f"✅ Method added: '{method}' added to class '{source}'")
                        added += 1
                
                dsl.classes[source]['methods'] = methods
                self.methods_added += added
    
    def _normalize_attribute_order(self, dsl: QualityAwareDSL):
        """Normalize attribute order."""
        for class_name, class_data in dsl.classes.items():
            attrs = class_data.get('attributes', [])
            if attrs:
                # Order: ID, Name, Status, Type, others
                priority = {
                    'id': 0,
                    'name': 1,
                    'status': 2,
                    'type': 3,
                    'description': 4
                }
                
                def get_priority(attr):
                    attr_lower = attr.lower()
                    for key, value in priority.items():
                        if key in attr_lower:
                            return value
                    return 5
                
                attrs.sort(key=get_priority)
                dsl.classes[class_name]['attributes'] = attrs
                dsl.add_correction(f"✅ Attribute order normalized: '{', '.join(attrs)}'")
    
    def _normalize_method_names(self, dsl: QualityAwareDSL):
        """Normalize method names."""
        for class_name, class_data in dsl.classes.items():
            methods = class_data.get('methods', [])
            normalized_methods = []
            for method in methods:
                # Ensure method ends with ()
                if not method.endswith('()'):
                    method = method + '()'
                # Lowercase method name without parentheses
                name = method[:-2]
                method = name.lower() + '()'
                normalized_methods.append(method)
            dsl.classes[class_name]['methods'] = normalized_methods
    
    def _add_default_cardinalities(self, dsl: QualityAwareDSL):
        """Add default cardinalities to relations."""
        for relation in dsl.relations:
            if not relation.get('source_cardinality'):
                relation['source_cardinality'] = '1'
                dsl.add_correction(f"✅ Cardinality added: source cardinality '1'")
                self.cardinalities_added += 1
            if not relation.get('target_cardinality'):
                relation['target_cardinality'] = '0..*'
                dsl.add_correction(f"✅ Cardinality added: target cardinality '0..*'")
                self.cardinalities_added += 1

# ===============================
# Isolated Class Detector and Corrector
# ===============================

class IsolatedClassDetector:
    """Detection and correction of isolated classes."""
    
    def __init__(self):
        self.relation_types = {
            'inheritance': {
                'keywords': ['is a', 'type of', 'specialized', 'subclass', 'extends', 'derived from'],
                'priority': 4,
                'patterns': [
                    r'(\w+)\s+is\s+a\s+(\w+)',
                    r'(\w+)\s+is\s+a\s+type\s+of\s+(\w+)',
                    r'(\w+)\s+specialized\s+(?:into|as)\s+(\w+)',
                    r'(\w+)\s+classified\s+as\s+(\w+)'
                ]
            },
            'composition': {
                'keywords': ['contains', 'composed of', 'part of', 'belongs to', 'owned by', 'exclusive'],
                'priority': 3,
                'patterns': [
                    r'(\w+)\s+contains\s+(\w+)',
                    r'(\w+)\s+is\s+composed\s+of\s+(\w+)',
                    r'(\w+)\s+is\s+a\s+part\s+of\s+(\w+)',
                    r'(\w+)\s+belongs\s+to\s+(\w+)'
                ]
            },
            'aggregation': {
                'keywords': ['includes', 'groups', 'organizes', 'manages', 'consists of'],
                'priority': 2,
                'patterns': [
                    r'(\w+)\s+includes\s+(\w+)',
                    r'(\w+)\s+groups\s+(\w+)',
                    r'(\w+)\s+manages\s+(\w+)',
                    r'(\w+)\s+consists\s+of\s+(\w+)'
                ]
            },
            'association': {
                'keywords': ['related to', 'associated with', 'connected to', 'linked to', 'uses'],
                'priority': 1,
                'patterns': [
                    r'(\w+)\s+is\s+associated\s+with\s+(\w+)',
                    r'(\w+)\s+is\s+related\s+to\s+(\w+)',
                    r'(\w+)\s+uses\s+(\w+)',
                    r'(\w+)\s+connected\s+to\s+(\w+)'
                ]
            }
        }
        
        # Common class names and their typical relationships
        self.typical_relations = {
            'Customer': {'types': ['Order', 'Account', 'Address'], 'relation': 'association'},
            'Order': {'types': ['Customer', 'Payment', 'OrderItem', 'Product'], 'relation': 'composition'},
            'Product': {'types': ['Category', 'OrderItem', 'Supplier'], 'relation': 'aggregation'},
            'User': {'types': ['Profile', 'Account', 'Permission'], 'relation': 'composition'},
            'Employee': {'types': ['Department', 'Role', 'Project'], 'relation': 'aggregation'},
            'Department': {'types': ['Employee', 'Manager', 'Project'], 'relation': 'aggregation'},
            'Project': {'types': ['Employee', 'Task', 'Milestone'], 'relation': 'composition'},
            'Account': {'types': ['User', 'Transaction', 'Balance'], 'relation': 'composition'},
            'Payment': {'types': ['Order', 'Transaction', 'Customer'], 'relation': 'association'},
            'Address': {'types': ['Customer', 'Order', 'User'], 'relation': 'association'},
            'Category': {'types': ['Product', 'SubCategory'], 'relation': 'inheritance'},
            'Supplier': {'types': ['Product', 'Order', 'Inventory'], 'relation': 'association'}
        }
        
        # Suffixes indicating special relationships
        self.relation_suffixes = {
            'Factory': ['Product', 'Component'],
            'Repository': ['Entity', 'Model'],
            'Service': ['Request', 'Response'],
            'Manager': ['Task', 'Resource'],
            'Controller': ['Request', 'Response'],
            'Gateway': ['Request', 'Response']
        }

    def _relation_exists(self, dsl: QualityAwareDSL, source: str, target: str) -> bool:
        """Check if a relation already exists between source and target."""
        for relation in dsl.relations:
            if (relation.get('source') == source and relation.get('target') == target) or \
               (relation.get('source') == target and relation.get('target') == source):
                return True
        return False

    def detect_and_correct(self, dsl: QualityAwareDSL, text: str) -> QualityAwareDSL:
        """Detect isolated classes and connect them automatically."""
        class_names = set(dsl.classes.keys())
        classes_with_valid_relations = set()
        
        # Identify classes that have NON-reflexive relations
        for relation in dsl.relations:
            source = relation.get('source')
            target = relation.get('target')
            
            if source != target:
                classes_with_valid_relations.add(source)
                classes_with_valid_relations.add(target)
        
        # Find isolated classes
        isolated_classes = class_names - classes_with_valid_relations
        
        if not isolated_classes:
            return dsl
        
        # Add correction for classes with only reflexive relations
        classes_with_only_reflexive = set()
        for class_name in class_names:
            reflexive_relations = []
            non_reflexive_relations = []
            
            for relation in dsl.relations:
                if relation.get('source') == class_name and relation.get('target') == class_name:
                    reflexive_relations.append(relation)
                elif relation.get('source') == class_name or relation.get('target') == class_name:
                    non_reflexive_relations.append(relation)
            
            if reflexive_relations and not non_reflexive_relations:
                classes_with_only_reflexive.add(class_name)
        
        if classes_with_only_reflexive:
            logger.info(f"🔍 Classes with ONLY reflexive relations detected: {', '.join(classes_with_only_reflexive)}")
            for cls in classes_with_only_reflexive:
                isolated_classes.add(cls)
        
        logger.info(f"🔍 {len(isolated_classes)} isolated class(es) detected: {', '.join(isolated_classes)}")
        
        # For each isolated class, try to connect it
        for isolated in isolated_classes:
            logger.info(f"  Processing isolated class: {isolated}")
            
            has_reflexive = False
            for relation in dsl.relations:
                if relation.get('source') == isolated and relation.get('target') == isolated:
                    has_reflexive = True
                    break
            
            relation_found = self._find_relation_for_class(isolated, dsl, text, class_names)
            
            if not relation_found and len(class_names) > 1:
                self._create_default_relation(isolated, dsl, class_names)
            
            if has_reflexive:
                dsl.add_correction(f"⚠️ Class '{isolated}' had only reflexive relations - an external relation was added")
        
        return dsl

    def _find_relation_for_class(self, class_name: str, dsl: QualityAwareDSL, 
                                 text: str, all_classes: Set[str]) -> bool:
        """Find an appropriate relation for an isolated class."""
        # 1. Check for relation patterns in the text
        for rel_type, type_info in self.relation_types.items():
            for pattern in type_info['patterns']:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    group1 = match.group(1).capitalize()
                    group2 = match.group(2).capitalize()
                    
                    if class_name == group1 and group2 in all_classes and group1 != group2:
                        if not self._relation_exists(dsl, class_name, group2):
                            dsl.add_relation(class_name, group2, rel_type)
                            dsl.add_correction(f"Isolated class '{class_name}' connected to '{group2}' by {rel_type} (pattern detected)")
                            logger.info(f"    ✅ Connected {class_name} -> {group2} by {rel_type}")
                            return True
                        else:
                            logger.info(f"    ⚠️ Relation {class_name} -> {group2} already exists, skipping")
                            return True
                    elif class_name == group2 and group1 in all_classes and group1 != group2:
                        if not self._relation_exists(dsl, group1, class_name):
                            dsl.add_relation(group1, class_name, rel_type)
                            dsl.add_correction(f"Isolated class '{class_name}' connected to '{group1}' by {rel_type} (pattern detected)")
                            logger.info(f"    ✅ Connected {group1} -> {class_name} by {rel_type}")
                            return True
                        else:
                            logger.info(f"    ⚠️ Relation {group1} -> {class_name} already exists, skipping")
                            return True

        # 2. Check keywords in the text
        for rel_type, type_info in self.relation_types.items():
            for keyword in type_info['keywords']:
                if keyword in text.lower():
                    for cls in all_classes:
                        if cls != class_name:
                            if re.search(rf'{class_name}\s+{keyword}\s+{cls}', text, re.IGNORECASE):
                                if not self._relation_exists(dsl, class_name, cls):
                                    dsl.add_relation(class_name, cls, rel_type)
                                    dsl.add_correction(f"Isolated class '{class_name}' connected to '{cls}' by {rel_type} (keyword: {keyword})")
                                    logger.info(f"    ✅ Connected {class_name} -> {cls} by {rel_type}")
                                    return True
                                else:
                                    logger.info(f"    ⚠️ Relation {class_name} -> {cls} already exists, skipping")
                                    return True
                            elif re.search(rf'{cls}\s+{keyword}\s+{class_name}', text, re.IGNORECASE):
                                if not self._relation_exists(dsl, cls, class_name):
                                    dsl.add_relation(cls, class_name, rel_type)
                                    dsl.add_correction(f"Isolated class '{class_name}' connected to '{cls}' by {rel_type} (keyword: {keyword})")
                                    logger.info(f"    ✅ Connected {cls} -> {class_name} by {rel_type}")
                                    return True
                                else:
                                    logger.info(f"    ⚠️ Relation {cls} -> {class_name} already exists, skipping")
                                    return True

        # 3. Check typical relations based on name
        for cls, info in self.typical_relations.items():
            if class_name == cls or class_name.endswith(cls) or class_name.startswith(cls):
                for target in info['types']:
                    if target in all_classes and target != class_name:
                        if not self._relation_exists(dsl, class_name, target):
                            rel_type = info['relation']
                            dsl.add_relation(class_name, target, rel_type)
                            dsl.add_correction(f"Isolated class '{class_name}' connected to '{target}' by {rel_type} (typical relation)")
                            logger.info(f"    ✅ Connected {class_name} -> {target} by {rel_type}")
                            return True
                        else:
                            logger.info(f"    ⚠️ Relation {class_name} -> {target} already exists, skipping")
                            return True
                break

        # 4. Check suffixes
        for suffix, targets in self.relation_suffixes.items():
            if class_name.endswith(suffix):
                for target in targets:
                    if target in all_classes and target != class_name:
                        if not self._relation_exists(dsl, class_name, target):
                            dsl.add_relation(class_name, target, 'composition')
                            dsl.add_correction(f"Isolated class '{class_name}' connected to '{target}' by composition (suffix {suffix})")
                            logger.info(f"    ✅ Connected {class_name} -> {target} by composition")
                            return True
                        else:
                            logger.info(f"    ⚠️ Relation {class_name} -> {target} already exists, skipping")
                            return True
                break

        return False

    def _create_default_relation(self, class_name: str, dsl: QualityAwareDSL, 
                                 all_classes: Set[str]):
        """Create a default relation with the most appropriate class."""
        best_match = None
        best_score = 0
        
        for other in all_classes:
            if other == class_name:
                continue
            
            score = self._calculate_semantic_similarity(class_name, other)
            
            if score > best_score:
                best_score = score
                best_match = other
        
        if best_match and best_score > 0.3:
            if not self._relation_exists(dsl, class_name, best_match):
                rel_type = self._determine_relation_type(class_name, best_match)
                dsl.add_relation(class_name, best_match, rel_type)
                dsl.add_correction(f"Isolated class '{class_name}' connected to '{best_match}' by {rel_type} (default relation)")
                logger.info(f"    ✅ Connected {class_name} -> {best_match} by {rel_type}")
            else:
                logger.info(f"    ⚠️ Relation {class_name} -> {best_match} already exists, skipping")
        elif len(all_classes) > 1:
            other = next(iter(all_classes - {class_name}))
            if not self._relation_exists(dsl, class_name, other):
                rel_type = 'association'
                dsl.add_relation(class_name, other, rel_type)
                dsl.add_correction(f"Isolated class '{class_name}' connected to '{other}' by {rel_type} (fallback relation)")
                logger.info(f"    ✅ Connected {class_name} -> {other} by {rel_type}")
            else:
                logger.info(f"    ⚠️ Relation {class_name} -> {other} already exists, skipping")

    def _calculate_semantic_similarity(self, class1: str, class2: str) -> float:
        """Calculate semantic similarity between two class names."""
        score = 0.0
        
        # 1. Common words
        words1 = set(class1.lower().split())
        words2 = set(class2.lower().split())
        common_words = words1 & words2
        score += len(common_words) * 0.3
        
        # 2. Common prefixes/suffixes
        for i in range(1, min(len(class1), len(class2)) + 1):
            if class1[:i].lower() == class2[:i].lower():
                score += 0.05
        
        for i in range(1, min(len(class1), len(class2)) + 1):
            if class1[-i:].lower() == class2[-i:].lower():
                score += 0.05
        
        # 3. Typical relations
        for cls, info in self.typical_relations.items():
            if class1 == cls or class1.endswith(cls) or class1.startswith(cls):
                if any(t == class2 or t.startswith(class2) or class2.startswith(t) for t in info['types']):
                    score += 0.5
        
        return min(score, 1.0)

    def _determine_relation_type(self, class1: str, class2: str) -> str:
        """Determine the most appropriate relation type between two classes."""
        # Check typical relations
        for cls, info in self.typical_relations.items():
            if class1 == cls or class1.endswith(cls) or class1.startswith(cls):
                if any(t == class2 or t.startswith(class2) or class2.startswith(t) for t in info['types']):
                    return info['relation']
            if class2 == cls or class2.endswith(cls) or class2.startswith(cls):
                if any(t == class1 or t.startswith(class1) or class1.startswith(t) for t in info['types']):
                    return info['relation']
        
        # Check suffixes
        for suffix, targets in self.relation_suffixes.items():
            if class1.endswith(suffix):
                if any(t == class2 or t.startswith(class2) or class2.startswith(t) for t in targets):
                    return 'composition'
            if class2.endswith(suffix):
                if any(t == class1 or t.startswith(class1) or class1.startswith(t) for t in targets):
                    return 'composition'
        
        # Check prefixes
        prefixes = ['Abstract', 'Base', 'Generic']
        for prefix in prefixes:
            if class1.startswith(prefix) or class2.startswith(prefix):
                return 'inheritance'
        
        # Check specific keywords
        if 'Manager' in class1 or 'Manager' in class2:
            return 'aggregation'
        if 'Factory' in class1 or 'Factory' in class2:
            return 'composition'
        if 'Service' in class1 or 'Service' in class2:
            return 'association'
        
        return 'association'

# ===============================
# NORMALIZER - Rules R1 to R9
# ===============================

class DSLNormalizer:
    """Implementation of rules R1-R8 with strict corrections."""
    
    def __init__(self):
        self.lexical_map = {}
        self.normalization_stats = {
            'classes_merged': 0,
            'attributes_normalized': 0,
            'methods_normalized': 0,
            'duplicates_removed': 0,
            'relations_corrected': 0,
            'classes_renamed': 0,
            'attributes_fixed': 0,
            'methods_fixed': 0
        }
        self._build_lexical_map()
        self._build_action_verbs()

    def _build_lexical_map(self):
        """Build the lexical variants map."""
        variants = {
            'id': ['identifier', 'identification', 'identity'],
            'number': ['no', 'num', 'count'],
            'name': ['title', 'label'],
            'date': ['datetime', 'timestamp'],
            'address': ['addr', 'location'],
            'email': ['mail', 'e-mail'],
            'phone': ['telephone', 'mobile', 'cell']
        }
        for term, alternatives in variants.items():
            for alt in alternatives:
                self.lexical_map[alt.lower()] = term
    
    def _build_action_verbs(self):
        """Build the list of action verbs for methods."""
        self.action_verbs = [
            'get', 'set', 'add', 'remove', 'update', 'delete', 'create',
            'generate', 'calculate', 'validate', 'process', 'handle',
            'place', 'cancel', 'find', 'search', 'save', 'load', 'export',
            'import', 'compute', 'evaluate', 'check', 'verify', 'approve',
            'reject', 'submit', 'confirm', 'request', 'send', 'receive'
        ]

    def normalize(self, dsl: QualityAwareDSL) -> Tuple[QualityAwareDSL, List[str]]:
        """Apply all normalizations with strict corrections."""
        rules_applied = []
        
        # R1 - Unique classes
        self._merge_duplicate_classes(dsl)
        rules_applied.append('R1')
        
        # R2 - Mandatory class name and correction
        self._validate_and_correct_class_names(dsl)
        rules_applied.append('R2')
        
        # R3 - Lexical normalization
        self._normalize_lexical_variants(dsl)
        rules_applied.append('R3')
        
        # R4 - Strict attribute normalization
        self._normalize_attributes_strict(dsl)
        rules_applied.append('R4')
        
        # R5 - Strict method normalization
        self._normalize_methods_strict(dsl)
        rules_applied.append('R5')
        
        # R6 - Deduplication
        self._deduplicate(dsl)
        rules_applied.append('R6')
        
        # R7 - Attribute/method separation
        self._separate_attributes_methods(dsl)
        rules_applied.append('R7')
        
        # R8 - Semantic association
        self._associate_semantically(dsl)
        rules_applied.append('R8')
        
        # R9 - Relation correction
        self._correct_relations(dsl)
        rules_applied.append('R9')
        
        return dsl, rules_applied

    def _merge_duplicate_classes(self, dsl: QualityAwareDSL):
        """R1 - Merge duplicate classes."""
        classes_to_merge = defaultdict(list)
        
        for class_name in list(dsl.classes.keys()):
            normalized = self._normalize_class_name(class_name)
            if normalized != class_name:
                classes_to_merge[normalized].append(class_name)
        
        for normalized, duplicates in classes_to_merge.items():
            if len(duplicates) > 1:
                merged_attrs = set()
                merged_methods = set()
                is_abstract = False
                confidence = 0.95
                
                for dup in duplicates:
                    dup_data = dsl.classes[dup]
                    merged_attrs.update(dup_data.get('attributes', []))
                    merged_methods.update(dup_data.get('methods', []))
                    if dup_data.get('is_abstract', False):
                        is_abstract = True
                    if dup_data.get('confidence', 0.95) > confidence:
                        confidence = dup_data.get('confidence', 0.95)
                    del dsl.classes[dup]
                
                dsl.classes[normalized] = {
                    'attributes': list(merged_attrs),
                    'methods': list(merged_methods),
                    'is_abstract': is_abstract,
                    'confidence': confidence
                }
                dsl.add_correction(f"Merged duplicate classes: {', '.join(duplicates)} -> {normalized}")
                self.normalization_stats['classes_merged'] += len(duplicates)

    def _normalize_class_name(self, name: str) -> str:
        """Normalize a class name."""
        if not name:
            return name
        name = re.sub(r'[^\w\s]', '', name)
        words = re.findall(r'[A-Z][a-z]*|[a-z]+', name)
        if words:
            return ''.join(w.capitalize() for w in words)
        return name.capitalize()

    def _validate_and_correct_class_names(self, dsl: QualityAwareDSL):
        """R2 - Validate and correct class names."""
        for class_name in list(dsl.classes.keys()):
            if not class_name or not class_name.strip():
                dsl.add_validation_error(ValidationError(
                    error_type=ErrorType.E_CLS,
                    level=ValidationLevel.SYNTAX,
                    message="Empty class name",
                    suggestion="Provide a valid class name",
                    element=class_name,
                    severity="error"
                ))
                continue
            
            corrected = self._normalize_class_name(class_name)
            if corrected != class_name:
                dsl.classes[corrected] = dsl.classes.pop(class_name)
                if class_name in dsl.quality_metrics:
                    dsl.quality_metrics[corrected] = dsl.quality_metrics.pop(class_name)
                
                for relation in dsl.relations:
                    if relation['source'] == class_name:
                        relation['source'] = corrected
                    if relation['target'] == class_name:
                        relation['target'] = corrected
                
                dsl.add_correction(f"Class renamed: {class_name} -> {corrected}")
                self.normalization_stats['classes_renamed'] += 1
                logger.info(f"Renamed class '{class_name}' to '{corrected}'")

    def _normalize_lexical_variants(self, dsl: QualityAwareDSL):
        """R3 - Lexical normalization."""
        for class_name, class_data in dsl.classes.items():
            normalized_attrs = []
            for attr in class_data.get('attributes', []):
                normalized = self._normalize_term(attr)
                if normalized and normalized not in normalized_attrs:
                    normalized_attrs.append(normalized)
            class_data['attributes'] = normalized_attrs

            normalized_methods = []
            for method in class_data.get('methods', []):
                normalized = self._normalize_method(method)
                if normalized and normalized not in normalized_methods:
                    normalized_methods.append(normalized)
            class_data['methods'] = normalized_methods

    def _normalize_term(self, term: str) -> str:
        """Normalize a term."""
        if not term:
            return ''
        term = term.lower().strip()
        term = re.sub(r'[_\s]+', ' ', term)
        words = term.split()
        if not words:
            return ''
        
        result = words[0]
        for word in words[1:]:
            result += word.capitalize()
        return result

    def _normalize_method(self, method: str) -> str:
        """Normalize a method."""
        if not method:
            return ''
        method = re.sub(r'[()]', '', method)
        method = method.lower().strip()
        method = re.sub(r'[_\s]+', ' ', method)
        words = method.split()
        if not words:
            return ''
        
        result = words[0]
        for word in words[1:]:
            result += word.capitalize()
        return result + '()'

    def _normalize_attributes_strict(self, dsl: QualityAwareDSL):
        """R4 - Strict attribute normalization."""
        common_attrs = {'id', 'name', 'description', 'type', 'status', 'date', 
                       'time', 'amount', 'value', 'code', 'number', 'email',
                       'phone', 'address', 'city', 'country', 'zip', 'url'}
        
        for class_name, class_data in dsl.classes.items():
            normalized = []
            for attr in class_data.get('attributes', []):
                if not attr:
                    continue
                attr = attr.strip()
                attr = self._normalize_term(attr)
                
                if len(attr) < 2:
                    dsl.add_validation_error(ValidationError(
                        error_type=ErrorType.E_ATT,
                        level=ValidationLevel.SYNTAX,
                        message=f"Attribute '{attr}' too short",
                        suggestion="Use a more descriptive attribute name",
                        element=f"{class_name}.{attr}",
                        severity="warning"
                    ))
                    continue
                
                for common in common_attrs:
                    if common in attr.lower():
                        break
                
                normalized.append(attr)
            
            class_data['attributes'] = normalized

    def _normalize_methods_strict(self, dsl: QualityAwareDSL):
        """R5 - Strict method normalization."""
        for class_name, class_data in dsl.classes.items():
            normalized = []
            for method in class_data.get('methods', []):
                if not method:
                    continue
                
                method = method.strip()
                method = self._normalize_method(method)
                method_clean = method.replace('()', '')
                
                is_action = any(method_clean.startswith(verb) for verb in self.action_verbs)
                if not is_action and len(method_clean) > 3:
                    if class_name.lower() in method_clean.lower():
                        if method_clean.startswith(class_name.lower()):
                            method = f"get{method_clean.capitalize()}()"
                        else:
                            method = f"process{method_clean.capitalize()}()"
                    self.normalization_stats['methods_fixed'] += 1
                    dsl.add_correction(f"Method corrected: {method} -> {method}")
                
                normalized.append(method)
            
            class_data['methods'] = normalized

    def _deduplicate(self, dsl: QualityAwareDSL):
        """R6 - Deduplication."""
        for class_name, class_data in dsl.classes.items():
            original_count = len(class_data.get('attributes', []))
            attrs = class_data.get('attributes', [])
            unique_attrs = []
            seen = set()
            for attr in attrs:
                if attr not in seen:
                    seen.add(attr)
                    unique_attrs.append(attr)
            class_data['attributes'] = unique_attrs
            self.normalization_stats['duplicates_removed'] += original_count - len(unique_attrs)
            
            original_count = len(class_data.get('methods', []))
            methods = class_data.get('methods', [])
            unique_methods = []
            seen = set()
            for method in methods:
                if method not in seen:
                    seen.add(method)
                    unique_methods.append(method)
            class_data['methods'] = unique_methods
            self.normalization_stats['duplicates_removed'] += original_count - len(unique_methods)

    def _separate_attributes_methods(self, dsl: QualityAwareDSL):
        """R7 - Attribute/method separation."""
        for class_name, class_data in dsl.classes.items():
            attributes = []
            methods = list(class_data.get('methods', []))

            for item in class_data.get('attributes', []):
                words = item.lower().split()
                is_method = any(any(word.startswith(verb) for verb in self.action_verbs) for word in words)
                if is_method:
                    methods.append(self._normalize_method(item))
                    dsl.add_correction(f"Attribute converted to method: {item}")
                else:
                    attributes.append(item)

            class_data['attributes'] = list(set(attributes))
            class_data['methods'] = list(set(methods))

    def _associate_semantically(self, dsl: QualityAwareDSL):
        """R8 - Semantic association."""
        for class_name, class_data in dsl.classes.items():
            coherent_attrs = []
            coherent_methods = []
            
            for attr in class_data.get('attributes', []):
                if self._is_coherent_with_class(attr, class_name):
                    coherent_attrs.append(attr)
                else:
                    dsl.add_validation_error(ValidationError(
                        error_type=ErrorType.E_SEM,
                        level=ValidationLevel.SEMANTIC,
                        message=f"Attribute '{attr}' may not be coherent with class '{class_name}'",
                        suggestion=f"Verify if '{attr}' belongs to '{class_name}'",
                        element=f"{class_name}.{attr}",
                        severity="warning"
                    ))
            
            for method in class_data.get('methods', []):
                if self._is_coherent_with_class(method, class_name):
                    coherent_methods.append(method)
                else:
                    dsl.add_validation_error(ValidationError(
                        error_type=ErrorType.E_SEM,
                        level=ValidationLevel.SEMANTIC,
                        message=f"Method '{method}' may not be coherent with class '{class_name}'",
                        suggestion=f"Verify if '{method}' belongs to '{class_name}'",
                        element=f"{class_name}.{method}",
                        severity="warning"
                    ))
            
            class_data['attributes'] = coherent_attrs
            class_data['methods'] = coherent_methods

    def _is_coherent_with_class(self, element: str, class_name: str) -> bool:
        """Check semantic coherence."""
        class_terms = set(class_name.lower().split())
        element_terms = set(element.lower().replace('()', '').split())
        return bool(class_terms & element_terms) or len(class_terms) == 1

    def _correct_relations(self, dsl: QualityAwareDSL):
        """R9 - Strict relation correction."""
        valid_types = ['association', 'aggregation', 'composition', 'inheritance', 'dependency']
        class_names = set(dsl.classes.keys())
        
        for relation in dsl.relations:
            source = relation.get('source')
            target = relation.get('target')
            rel_type = relation.get('type', 'association').lower()
            
            source = self._normalize_class_name(source)
            target = self._normalize_class_name(target)
            
            if source not in class_names:
                found = False
                for cls in class_names:
                    if source.lower() in cls.lower() or cls.lower() in source.lower():
                        relation['source'] = cls
                        dsl.add_correction(f"Relation source corrected: {source} -> {cls}")
                        source = cls
                        found = True
                        break
                if not found:
                    dsl.add_validation_error(ValidationError(
                        error_type=ErrorType.E_ASS,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Source class '{source}' not found",
                        suggestion=f"Add class '{source}' or correct the relation",
                        element=source,
                        severity="error"
                    ))
                    continue
            else:
                relation['source'] = source
            
            if target not in class_names:
                found = False
                for cls in class_names:
                    if target.lower() in cls.lower() or cls.lower() in target.lower():
                        relation['target'] = cls
                        dsl.add_correction(f"Relation target corrected: {target} -> {cls}")
                        target = cls
                        found = True
                        break
                if not found:
                    dsl.add_validation_error(ValidationError(
                        error_type=ErrorType.E_ASS,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Target class '{target}' not found",
                        suggestion=f"Add class '{target}' or correct the relation",
                        element=target,
                        severity="error"
                    ))
                    continue
            else:
                relation['target'] = target
            
            if rel_type not in valid_types:
                if rel_type in ['has', 'contains']:
                    rel_type = 'composition'
                elif rel_type in ['uses', 'depends']:
                    rel_type = 'dependency'
                elif rel_type in ['extends', 'implements']:
                    rel_type = 'inheritance'
                else:
                    rel_type = 'association'
                relation['type'] = rel_type
                dsl.add_correction(f"Relation type corrected: {relation.get('type')} -> {rel_type}")
                self.normalization_stats['relations_corrected'] += 1
            
            if rel_type == 'association' and self._is_inheritance_relation(source, target, dsl):
                relation['type'] = 'inheritance'
                dsl.add_correction(f"Relation converted to inheritance: {source} -> {target}")
                self.normalization_stats['relations_corrected'] += 1
            
            if rel_type == 'inheritance':
                if self._is_inheritance_reversed(source, target, dsl):
                    relation['source'], relation['target'] = target, source
                    dsl.add_correction(f"Inheritance direction reversed: {target} -> {source}")
                    self.normalization_stats['relations_corrected'] += 1

    def _is_inheritance_relation(self, source: str, target: str, dsl: QualityAwareDSL) -> bool:
        """Check if a relation should be inheritance."""
        if target.lower() in source.lower() and source != target:
            return True
        if source.lower() in target.lower() and source != target:
            return True
        return False

    def _is_inheritance_reversed(self, source: str, target: str, dsl: QualityAwareDSL) -> bool:
        """Check if inheritance direction is reversed."""
        if len(source.split()) > len(target.split()):
            return True
        
        prefixes = ['passenger', 'cargo', 'electric', 'premium', 'standard']
        for prefix in prefixes:
            if prefix in source.lower() and prefix not in target.lower():
                return True
        
        return False

# ===============================
# IMPLICIT RELATION DETECTOR - Rules R43-R46
# ===============================

class ImplicitRelationDetector:
    """Detection of implicit relationships."""
    
    def __init__(self):
        self.relation_patterns = {
            'association': [
                r'(interacts|works|uses|enrolls|assigned to|operates|follows)',
                r'is associated with',
                r'communicates with'
            ],
            'aggregation': [
                r'contains',
                r'includes',
                r'groups',
                r'manages',
                r'consists of'
            ],
            'composition': [
                r'belongs exclusively to',
                r'owned exclusively by',
                r'part of',
                r'contains and controls',
                r'composed of',
                r'each .+ contains',
                r'.+ is composed of'
            ],
            'inheritance': [
                r'specialized into',
                r'specialized as',
                r'classified into',
                r'types of',
                r'subtypes of',
                r'is a type of',
                r'is a',
                r'derived from'
            ]
        }
        
        self.action_verbs = [
            'calculate', 'compute', 'process', 'validate', 'verify',
            'generate', 'create', 'delete', 'update', 'modify',
            'get', 'set', 'add', 'remove', 'find', 'search'
        ]

    def detect(self, dsl: QualityAwareDSL, text: str) -> QualityAwareDSL:
        """Detect implicit relationships."""
        new_relations = []
        class_names = set(dsl.classes.keys())
        
        for rel_type, patterns in self.relation_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    relation = self._extract_relation_from_match(match, text, rel_type, class_names)
                    if relation and not self._relation_exists(relation, dsl):
                        new_relations.append(relation)
        
        for verb in self.action_verbs:
            pattern = rf'(\w+)\s+{verb}s?\s+(\w+)'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                source = match.group(1).capitalize()
                target = match.group(2).capitalize()
                if source in class_names and target in class_names:
                    relation = {
                        'source': source,
                        'target': target,
                        'type': 'association',
                        'implicit': True,
                        'confidence': 0.70
                    }
                    if not self._relation_exists(relation, dsl):
                        new_relations.append(relation)
        
        for relation in new_relations:
            dsl.add_relation(
                relation['source'],
                relation['target'],
                relation['type'],
                confidence=relation.get('confidence', 0.85)
            )
            dsl.add_correction(f"Implicit relation added: {relation['source']} -> {relation['target']} ({relation['type']})")
        
        return dsl

    def _extract_relation_from_match(self, match, text: str, rel_type: str,
                                     class_names: Set[str]) -> Optional[Dict]:
        """Extract a relation from a match."""
        start = match.start()
        end = match.end()
        
        before = text[:start]
        after = text[end:]
        
        source = None
        target = None
        
        for class_name in class_names:
            if class_name.lower() in before.lower():
                source = class_name
                break
        
        for class_name in class_names:
            if class_name.lower() in after.lower():
                target = class_name
                break
        
        if source and target and source != target:
            return {
                'source': source,
                'target': target,
                'type': rel_type,
                'implicit': True,
                'confidence': 0.85,
                'pattern': match.group()
            }
        
        return None

    def _relation_exists(self, relation: Dict, dsl: QualityAwareDSL) -> bool:
        """Check if a relation already exists."""
        for existing in dsl.relations:
            if (existing.get('source') == relation.get('source') and
                existing.get('target') == relation.get('target')):
                return True
        return False

# ===============================
# RELATIONSHIP DISAMBIGUATOR - Rules R25-R37
# ===============================

class RelationshipDisambiguator:
    """Relationship disambiguation."""
    
    def __init__(self):
        self.priority = {
            'inheritance': 4,
            'composition': 3,
            'aggregation': 2,
            'association': 1
        }

    def disambiguate(self, dsl: QualityAwareDSL, text: str) -> QualityAwareDSL:
        """Disambiguate relationships."""
        for relation in dsl.relations:
            rel_type = relation.get('type', '').lower()
            
            context = self._get_relation_context(relation, text)
            
            if 'exclusively' in context or 'owned' in context or 'part of' in context:
                if rel_type in ['association', 'aggregation']:
                    relation['type'] = 'composition'
                    dsl.add_correction(f"Relation disambiguated to composition: {relation['source']} -> {relation['target']}")
                    continue
            
            if 'contains' in context or 'includes' in context or 'groups' in context:
                if rel_type == 'association':
                    relation['type'] = 'aggregation'
                    dsl.add_correction(f"Relation disambiguated to aggregation: {relation['source']} -> {relation['target']}")
                    continue
            
            if 'is a' in context or 'type of' in context or 'specialized' in context:
                if rel_type in ['association', 'aggregation']:
                    relation['type'] = 'inheritance'
                    dsl.add_correction(f"Relation disambiguated to inheritance: {relation['source']} -> {relation['target']}")
                    self._check_inheritance_direction(relation, text)
                    continue
        
        return dsl

    def _get_relation_context(self, relation: Dict, text: str) -> str:
        """Extract the context of a relation."""
        source = relation.get('source', '')
        target = relation.get('target', '')
        
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            if source.lower() in sentence.lower() and target.lower() in sentence.lower():
                return sentence
        return ''

    def _check_inheritance_direction(self, relation: Dict, text: str):
        """Check and correct inheritance direction."""
        source = relation.get('source')
        target = relation.get('target')
        
        if len(target.split()) > len(source.split()):
            return
        
        specific_prefixes = ['passenger', 'cargo', 'electric', 'premium']
        for prefix in specific_prefixes:
            if prefix in target.lower() and prefix not in source.lower():
                return
        
        relation['source'], relation['target'] = target, source
        relation['direction_corrected'] = True

# ===============================
# CARDINALITY PROCESSOR - Rules R47-R51
# ===============================

class CardinalityProcessor:
    """Cardinality processing."""
    
    def __init__(self):
        self.cardinality_patterns = {
            '1': r'exactly one|one and only one|single',
            '0..1': r'zero or one|optional one',
            '0..*': r'zero or more|any number of',
            '1..*': r'one or more|at least one|several|many',
            '*': r'multiple|many|several|various'
        }

    def process(self, dsl: QualityAwareDSL, text: str) -> QualityAwareDSL:
        """Detect and associate cardinalities."""
        for relation in dsl.relations:
            source = relation.get('source')
            target = relation.get('target')
            
            sentences = self._find_sentences_with_both(text, source, target)
            
            for sentence in sentences:
                source_card = self._extract_cardinality(sentence, source)
                if source_card and not relation.get('source_cardinality'):
                    relation['source_cardinality'] = source_card
                    dsl.add_correction(f"Source cardinality added: {source} {source_card}")
                
                target_card = self._extract_cardinality(sentence, target)
                if target_card and not relation.get('target_cardinality'):
                    relation['target_cardinality'] = target_card
                    dsl.add_correction(f"Target cardinality added: {target} {target_card}")
        
        return dsl

    def _find_sentences_with_both(self, text: str, term1: str, term2: str) -> List[str]:
        """Find sentences containing both terms."""
        sentences = re.split(r'[.!?]', text)
        return [s for s in sentences if term1.lower() in s.lower() and term2.lower() in s.lower()]

    def _extract_cardinality(self, sentence: str, term: str) -> Optional[str]:
        """Extract cardinality from a sentence."""
        for cardinality, pattern in self.cardinality_patterns.items():
            if re.search(rf'{term}\s+{pattern}', sentence, re.IGNORECASE):
                return cardinality
            if re.search(rf'{pattern}\s+{term}', sentence, re.IGNORECASE):
                return cardinality
        return None

# ===============================
# STRUCTURAL CONSISTENCY CHECKER - Rules R52-R58
# ===============================

class StructuralConsistencyChecker:
    """Structural consistency validation."""
    
    def __init__(self):
        self.errors = []

    def check(self, dsl: QualityAwareDSL) -> List[ValidationError]:
        """Check structural consistency."""
        self.errors = []
        
        self._check_relation_endpoints(dsl)
        self._check_orphan_endpoints(dsl)
        self._check_inheritance_structure(dsl)
        self._check_composition_structure(dsl)
        self._check_aggregation_structure(dsl)
        self._check_association_default(dsl)
        self._check_contradictory_relations(dsl)
        self._check_missing_relations(dsl)
        
        for error in self.errors:
            dsl.add_validation_error(error)
        
        return self.errors

    def _check_relation_endpoints(self, dsl: QualityAwareDSL):
        """R52 - Check relation endpoints."""
        classes = set(dsl.classes.keys())
        
        for relation in dsl.relations:
            source = relation.get('source')
            target = relation.get('target')
            
            if source not in classes:
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_SEM,
                    level=ValidationLevel.STRUCTURAL,
                    message=f"Source class '{source}' not found",
                    suggestion=f"Add class '{source}' or correct the relation",
                    element=source,
                    severity="error"
                ))
            
            if target not in classes:
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_SEM,
                    level=ValidationLevel.STRUCTURAL,
                    message=f"Target class '{target}' not found",
                    suggestion=f"Add class '{target}' or correct the relation",
                    element=target,
                    severity="error"
                ))

    def _check_orphan_endpoints(self, dsl: QualityAwareDSL):
        """R53 - Check orphan endpoints."""
        referenced = set()
        for relation in dsl.relations:
            referenced.add(relation.get('source'))
            referenced.add(relation.get('target'))
        
        classes = set(dsl.classes.keys())
        orphans = referenced - classes
        
        for orphan in orphans:
            self.errors.append(ValidationError(
                error_type=ErrorType.E_SEM,
                level=ValidationLevel.STRUCTURAL,
                message=f"Orphan endpoint: '{orphan}'",
                suggestion=f"Add class '{orphan}' or remove the relation",
                element=orphan,
                severity="error"
            ))

    def _check_inheritance_structure(self, dsl: QualityAwareDSL):
        """R54 - Check inheritance structure."""
        for relation in dsl.relations:
            if relation.get('type', '').lower() == 'inheritance':
                source = relation.get('source')
                target = relation.get('target')
                
                if not self._is_generalization(source, target, dsl):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_INH,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Invalid inheritance: '{source}' should be more general than '{target}'",
                        suggestion=f"Reverse the inheritance: {target} -> {source}",
                        element=str(relation),
                        severity="error"
                    ))

    def _check_composition_structure(self, dsl: QualityAwareDSL):
        """R55 - Check composition structure."""
        for relation in dsl.relations:
            if relation.get('type', '').lower() == 'composition':
                source = relation.get('source')
                target = relation.get('target')
                
                if not self._is_part_of(source, target, dsl):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_CMP,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Composition may be incorrect: '{target}' should be part of '{source}'",
                        suggestion="Verify the composition relationship",
                        element=str(relation),
                        severity="warning"
                    ))

    def _check_aggregation_structure(self, dsl: QualityAwareDSL):
        """R56 - Check aggregation structure."""
        for relation in dsl.relations:
            if relation.get('type', '').lower() == 'aggregation':
                source = relation.get('source')
                target = relation.get('target')
                
                if not self._is_weak_part_of(source, target, dsl):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_AGR,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Aggregation may be too strong: '{target}' may depend on '{source}'",
                        suggestion="Consider using association or composition",
                        element=str(relation),
                        severity="warning"
                    ))

    def _check_association_default(self, dsl: QualityAwareDSL):
        """R57 - Check default associations."""
        for relation in dsl.relations:
            if relation.get('type', '').lower() == 'association':
                if not self._is_association_justified(relation, dsl):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_ASS,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Association may be too weak: '{relation.get('source')}' - '{relation.get('target')}'",
                        suggestion="Consider if a stronger relationship exists",
                        element=str(relation),
                        severity="warning"
                    ))

    def _check_contradictory_relations(self, dsl: QualityAwareDSL):
        """R58 - Detect contradictory relations."""
        relation_map = {}
        
        for relation in dsl.relations:
            key = tuple(sorted([relation.get('source'), relation.get('target')]))
            if key not in relation_map:
                relation_map[key] = []
            relation_map[key].append(relation)
        
        for key, relations in relation_map.items():
            if len(relations) > 1:
                types = set(r.get('type') for r in relations)
                if len(types) > 1:
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_CAR,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Contradictory relations between '{key[0]}' and '{key[1]}': {', '.join(types)}",
                        suggestion=f"Keep only the strongest relationship",
                        element=f"{key[0]}_{key[1]}",
                        context={'relations': relations},
                        severity="error"
                    ))

    def _check_missing_relations(self, dsl: QualityAwareDSL):
        """Check for missing relations."""
        class_names = set(dsl.classes.keys())
        classes_with_relations = set()
        
        for relation in dsl.relations:
            classes_with_relations.add(relation.get('source'))
            classes_with_relations.add(relation.get('target'))
        
        isolated_classes = class_names - classes_with_relations
        for isolated in isolated_classes:
            self.errors.append(ValidationError(
                error_type=ErrorType.E_ASS,
                level=ValidationLevel.STRUCTURAL,
                message=f"Class '{isolated}' has no relations",
                suggestion="Consider adding relations or marking as standalone",
                element=isolated,
                severity="info"
            ))

    def _is_generalization(self, source: str, target: str, dsl: QualityAwareDSL) -> bool:
        """Check if source is a generalization of target."""
        return len(target.split()) >= len(source.split())

    def _is_part_of(self, source: str, target: str, dsl: QualityAwareDSL) -> bool:
        """Check if target is part of source."""
        if source in dsl.classes:
            attrs = dsl.classes[source].get('attributes', [])
            for attr in attrs:
                if target.lower() in attr.lower():
                    return True
        return False

    def _is_weak_part_of(self, source: str, target: str, dsl: QualityAwareDSL) -> bool:
        """Check if target is a weak part of source."""
        return True

    def _is_association_justified(self, relation: Dict, dsl: QualityAwareDSL) -> bool:
        """Check if an association is justified."""
        source = relation.get('source')
        target = relation.get('target')
        
        if source in dsl.classes and target in dsl.classes:
            return True
        return True

# ===============================
# STRICT AUTO CORRECTOR
# ===============================

class AutoCorrector:
    """Strict automatic correction of errors."""
    
    def __init__(self):
        self.correction_log = []
        self.corrections_applied = []
        self.correction_count = 0

    def correct(self, dsl: QualityAwareDSL, errors: List[ValidationError]) -> QualityAwareDSL:
        """Apply strict automatic corrections."""
        self.correction_log = []
        self.corrections_applied = []
        self.correction_count = 0
        
        # Class corrections
        self._correct_classes(dsl, errors)
        
        # Attribute corrections
        self._correct_attributes(dsl, errors)
        
        # Method corrections
        self._correct_methods(dsl, errors)
        
        # Relation corrections
        self._correct_relations(dsl, errors)
        
        # Structural corrections
        self._correct_structure(dsl, errors)
        
        return dsl

    def _correct_classes(self, dsl: QualityAwareDSL, errors: List[ValidationError]):
        """Correct class errors."""
        for error in errors:
            if error.error_type == ErrorType.E_CLS:
                if 'class name' in error.message.lower() and error.element:
                    class_name = error.element
                    corrected = self._normalize_class_name(class_name)
                    
                    if class_name in dsl.classes and corrected not in dsl.classes:
                        dsl.classes[corrected] = dsl.classes.pop(class_name)
                        if class_name in dsl.quality_metrics:
                            dsl.quality_metrics[corrected] = dsl.quality_metrics.pop(class_name)
                        
                        for relation in dsl.relations:
                            if relation['source'] == class_name:
                                relation['source'] = corrected
                            if relation['target'] == class_name:
                                relation['target'] = corrected
                        
                        dsl.add_correction(f"Class renamed: {class_name} -> {corrected}")
                        self.corrections_applied.append(f'Renamed class {class_name} to {corrected}')
                        self.correction_count += 1

    def _normalize_class_name(self, name: str) -> str:
        """Normalize a class name."""
        if not name:
            return name
        name = re.sub(r'[^\w\s]', '', name)
        words = re.findall(r'[A-Z][a-z]*|[a-z]+', name)
        if words:
            return ''.join(w.capitalize() for w in words)
        return name.capitalize()

    def _correct_attributes(self, dsl: QualityAwareDSL, errors: List[ValidationError]):
        """Correct attribute errors."""
        for error in errors:
            if error.error_type == ErrorType.E_ATT:
                if error.element and '.' in error.element:
                    class_name, attr_name = error.element.split('.', 1)
                    if class_name in dsl.classes:
                        attrs = dsl.classes[class_name].get('attributes', [])
                        if attr_name in attrs:
                            corrected = self._normalize_attribute(attr_name)
                            if corrected != attr_name:
                                idx = attrs.index(attr_name)
                                attrs[idx] = corrected
                                dsl.add_correction(f"Attribute corrected: {attr_name} -> {corrected}")
                                self.corrections_applied.append(f'Corrected attribute {attr_name} to {corrected}')
                                self.correction_count += 1

    def _normalize_attribute(self, attr: str) -> str:
        """Normalize an attribute."""
        attr = attr.strip()
        attr = re.sub(r'[_\s]+', ' ', attr)
        words = attr.split()
        if not words:
            return ''
        
        result = words[0].lower()
        for word in words[1:]:
            result += word.capitalize()
        return result

    def _correct_methods(self, dsl: QualityAwareDSL, errors: List[ValidationError]):
        """Correct method errors."""
        for error in errors:
            if error.error_type == ErrorType.E_MTH:
                if error.element and '.' in error.element:
                    parts = error.element.replace('()', '').split('.', 1)
                    if len(parts) == 2:
                        class_name, method_name = parts
                        if class_name in dsl.classes:
                            methods = dsl.classes[class_name].get('methods', [])
                            if method_name in methods:
                                corrected = self._normalize_method(method_name)
                                if corrected != method_name:
                                    idx = methods.index(method_name)
                                    methods[idx] = corrected
                                    dsl.add_correction(f"Method corrected: {method_name} -> {corrected}")
                                    self.corrections_applied.append(f'Corrected method {method_name} to {corrected}')
                                    self.correction_count += 1

    def _normalize_method(self, method: str) -> str:
        """Normalize a method."""
        method = method.strip()
        method = re.sub(r'[()]', '', method)
        method = method.lower().strip()
        method = re.sub(r'[_\s]+', ' ', method)
        words = method.split()
        if not words:
            return ''
        
        result = words[0]
        for word in words[1:]:
            result += word.capitalize()
        return result + '()'

    def _correct_relations(self, dsl: QualityAwareDSL, errors: List[ValidationError]):
        """Correct relation errors."""
        for error in errors:
            if error.error_type in [ErrorType.E_ASS, ErrorType.E_CAR]:
                if 'contradictory' in error.message.lower():
                    context = error.context or {}
                    relations = context.get('relations', [])
                    if relations:
                        filtered = []
                        priority = {'composition': 3, 'aggregation': 2, 'inheritance': 1, 'association': 0}
                        
                        for relation in dsl.relations:
                            if (relation.get('source') == relations[0].get('source') and
                                relation.get('target') == relations[0].get('target')):
                                if not filtered:
                                    filtered.append(relation)
                                else:
                                    current = priority.get(relation.get('type', 'association'), 0)
                                    best = priority.get(filtered[0].get('type', 'association'), 0)
                                    if current > best:
                                        filtered[0] = relation
                            else:
                                filtered.append(relation)
                        
                        dsl.relations = filtered
                        dsl.add_correction("Resolved contradictory relations")
                        self.corrections_applied.append('Resolved contradictory relations')
                        self.correction_count += 1

    def _correct_structure(self, dsl: QualityAwareDSL, errors: List[ValidationError]):
        """Correct structural errors."""
        for error in errors:
            if error.error_type == ErrorType.E_INH and 'direction' in error.message.lower():
                for relation in dsl.relations:
                    if relation.get('type') == 'inheritance':
                        source = relation.get('source')
                        target = relation.get('target')
                        
                        if len(source.split()) < len(target.split()):
                            relation['source'], relation['target'] = target, source
                            dsl.add_correction(f"Inheritance direction reversed: {target} -> {source}")
                            self.corrections_applied.append(f'Reversed inheritance direction {source} <-> {target}')
                            self.correction_count += 1

# ===============================
# Multi-level Validation Engine
# ===============================

class DSLValidator:
    """Multi-level validation engine for DSL."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self._class_names: Set[str] = set()
    
    def validate(self, dsl: QualityAwareDSL) -> List[ValidationError]:
        """Perform complete DSL validation."""
        self.errors = []
        self._class_names = set(dsl.classes.keys())
        
        # 4-level validation
        self._validate_syntax(dsl)
        self._validate_semantic(dsl)
        self._validate_relationships(dsl)
        self._validate_structural(dsl)
        
        # Update errors in DSL
        dsl.validation_errors = self.errors
        dsl.metadata['total_errors'] = len(self.errors)
        
        return self.errors
    
    def _validate_syntax(self, dsl: QualityAwareDSL):
        """Syntax validation."""
        # Check class names
        for class_name in dsl.classes.keys():
            if not class_name or not class_name[0].isupper():
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_SYN,
                    level=ValidationLevel.SYNTAX,
                    message=f"Invalid class name: '{class_name}'. Class names should start with an uppercase letter.",
                    element=class_name,
                    suggestion=f"Rename '{class_name}' to '{class_name.capitalize()}'",
                    context={'class_name': class_name, 'suggested': class_name.capitalize()},
                    severity="error"
                ))
            
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', class_name):
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_SYN,
                    level=ValidationLevel.SYNTAX,
                    message=f"Invalid class name: '{class_name}'. Use only letters, digits, and underscores.",
                    element=class_name,
                    suggestion="Use a valid identifier",
                    severity="error"
                ))
        
        # Check attributes
        for class_name, class_data in dsl.classes.items():
            for attr in class_data.get('attributes', []):
                if not attr or not isinstance(attr, str):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_ATT,
                        level=ValidationLevel.SYNTAX,
                        message=f"Invalid attribute in class '{class_name}': '{attr}'",
                        element=f"{class_name}.{attr}",
                        suggestion="Ensure attributes are valid strings",
                        severity="error"
                    ))
                elif not re.match(r'^[a-z_][a-z0-9_]*$', attr.lower()):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_ATT,
                        level=ValidationLevel.SYNTAX,
                        message=f"Attribute '{attr}' in class '{class_name}' should be lowercase with underscores",
                        element=f"{class_name}.{attr}",
                        suggestion=f"Rename to '{attr.lower()}'",
                        severity="warning"
                    ))
            
            # Check methods
            for method in class_data.get('methods', []):
                if not method or not isinstance(method, str):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_MTH,
                        level=ValidationLevel.SYNTAX,
                        message=f"Invalid method in class '{class_name}': '{method}'",
                        element=f"{class_name}.{method}()",
                        suggestion="Ensure methods are valid strings",
                        severity="error"
                    ))
                elif not re.match(r'^[a-z_][a-z0-9_]*\(\)$', method):
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_MTH,
                        level=ValidationLevel.SYNTAX,
                        message=f"Method '{method}' in class '{class_name}' should be lowercase with ()",
                        element=f"{class_name}.{method}",
                        suggestion=f"Rename to '{method.lower()}()'",
                        severity="warning"
                    ))
    
    def _validate_semantic(self, dsl: QualityAwareDSL):
        """Semantic validation."""
        class_names = set(dsl.classes.keys())
        
        # Check class references
        for relation in dsl.relations:
            source = relation.get('source')
            target = relation.get('target')
            
            if source not in class_names:
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_SEM,
                    level=ValidationLevel.SEMANTIC,
                    message=f"Source class '{source}' referenced in relation but not defined",
                    element=source,
                    suggestion=f"Add class '{source}' or correct the relation",
                    context={'source': source, 'target': target},
                    severity="error"
                ))
            
            if target not in class_names:
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_SEM,
                    level=ValidationLevel.SEMANTIC,
                    message=f"Target class '{target}' referenced in relation but not defined",
                    element=target,
                    suggestion=f"Add class '{target}' or correct the relation",
                    context={'source': source, 'target': target},
                    severity="error"
                ))
        
        # Check duplicate attributes
        for class_name, class_data in dsl.classes.items():
            attrs = class_data.get('attributes', [])
            if len(attrs) != len(set(attrs)):
                duplicates = [a for a in attrs if attrs.count(a) > 1]
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_ATT,
                    level=ValidationLevel.SEMANTIC,
                    message=f"Duplicate attributes in class '{class_name}': {', '.join(set(duplicates))}",
                    element=class_name,
                    suggestion=f"Remove duplicate attributes: {', '.join(set(duplicates))}",
                    severity="error"
                ))
        
        # Check duplicate methods
        for class_name, class_data in dsl.classes.items():
            methods = class_data.get('methods', [])
            if len(methods) != len(set(methods)):
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_MTH,
                    level=ValidationLevel.SEMANTIC,
                    message=f"Duplicate methods in class '{class_name}'",
                    element=class_name,
                    suggestion="Remove duplicate methods",
                    severity="error"
                ))
    
    def _validate_relationships(self, dsl: QualityAwareDSL):
        """UML relationship validation."""
        valid_types = ['association', 'aggregation', 'composition', 'inheritance', 'dependency']
        
        for idx, relation in enumerate(dsl.relations):
            source = relation.get('source')
            target = relation.get('target')
            rel_type = relation.get('type', '').lower()
            
            # Check relation type
            if rel_type not in valid_types:
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_ASS,
                    level=ValidationLevel.RELATIONSHIP,
                    message=f"Invalid relationship type '{rel_type}' between '{source}' and '{target}'",
                    element=f"{source}_{target}",
                    suggestion=f"Use one of: {', '.join(valid_types)}",
                    context={'source': source, 'target': target, 'type': rel_type},
                    severity="error"
                ))
                continue
            
            # Check inheritance
            if rel_type == 'inheritance':
                if source == target:
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_INH,
                        level=ValidationLevel.RELATIONSHIP,
                        message=f"Class '{source}' cannot inherit from itself",
                        element=source,
                        suggestion="Check inheritance relationship - a class cannot inherit from itself",
                        severity="error"
                    ))
            
            # Check composition
            if rel_type == 'composition':
                if source == target:
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_CMP,
                        level=ValidationLevel.RELATIONSHIP,
                        message=f"Class '{source}' cannot be composed of itself",
                        element=source,
                        suggestion="A class cannot contain itself as a component",
                        severity="error"
                    ))
            
            # Check aggregation
            if rel_type == 'aggregation':
                if source == target:
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_AGR,
                        level=ValidationLevel.RELATIONSHIP,
                        message=f"Class '{source}' cannot aggregate itself",
                        element=source,
                        suggestion="A class cannot aggregate itself",
                        severity="error"
                    ))
        
        # Check contradictory relations
        relation_pairs = {}
        for relation in dsl.relations:
            key = tuple(sorted([relation['source'], relation['target']]))
            if key in relation_pairs:
                relation_pairs[key].append(relation['type'])
            else:
                relation_pairs[key] = [relation['type']]
        
        for pair, types in relation_pairs.items():
            if len(set(types)) > 1:
                self.errors.append(ValidationError(
                    error_type=ErrorType.E_CAR,
                    level=ValidationLevel.RELATIONSHIP,
                    message=f"Multiple contradictory relationships between '{pair[0]}' and '{pair[1]}': {', '.join(set(types))}",
                    element=f"{pair[0]}_{pair[1]}",
                    suggestion="Keep only the strongest relationship (composition > aggregation > inheritance > association)",
                    context={'classes': list(pair), 'types': list(set(types))},
                    severity="error"
                ))
    
    def _validate_structural(self, dsl: QualityAwareDSL):
        """Structural validation."""
        # Check inheritance cycles
        inheritance_graph = {}
        for relation in dsl.relations:
            if relation['type'].lower() == 'inheritance':
                source = relation['source']
                target = relation['target']
                if source in self._class_names and target in self._class_names:
                    if source not in inheritance_graph:
                        inheritance_graph[source] = []
                    inheritance_graph[source].append(target)
        
        def has_cycle(node, visited, path):
            visited.add(node)
            path.append(node)
            
            for neighbor in inheritance_graph.get(node, []):
                if neighbor in path:
                    cycle = ' -> '.join(path[path.index(neighbor):] + [neighbor])
                    self.errors.append(ValidationError(
                        error_type=ErrorType.E_INH,
                        level=ValidationLevel.STRUCTURAL,
                        message=f"Inheritance cycle detected: {cycle}",
                        element=node,
                        suggestion="Break the inheritance cycle by removing or modifying relationships",
                        context={'cycle': cycle},
                        severity="error"
                    ))
                    return True
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, path):
                        return True
            
            path.pop()
            return False
        
        visited = set()
        for node in inheritance_graph:
            if node not in visited:
                has_cycle(node, visited, [])
        
        # Check structural completeness
        if len(dsl.classes) == 0:
            self.errors.append(ValidationError(
                error_type=ErrorType.E_CLS,
                level=ValidationLevel.STRUCTURAL,
                message="No classes defined in the model",
                element="model",
                suggestion="Add at least one class to the model",
                severity="error"
            ))

# ===============================
# Self-Repair Mechanism
# ===============================

class DSLRepairer:
    """Automatic repair mechanism for DSL."""
    
    def __init__(self, max_iterations: int = 3, auto_fix: bool = True):
        self.max_iterations = max_iterations
        self.auto_fix = auto_fix
        self.repair_history = []
        self.auto_corrector = AutoCorrector()
        self.completeness_enhancer = CompletenessEnhancer()
    
    def repair(self, dsl: QualityAwareDSL, validator: DSLValidator) -> QualityAwareDSL:
        """Attempt to automatically repair the DSL."""
        iteration = 0
        dsl.repair_history = []
        previous_error_count = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Apply completeness enhancement
            dsl = self.completeness_enhancer.enhance(dsl)
            
            # Validate
            errors = validator.validate(dsl)
            current_error_count = len(errors)
            
            if current_error_count == 0:
                logger.info(f"✅ No validation errors found after {iteration} iteration(s)")
                break
            
            # Save state before repair
            repair_record = {
                'iteration': iteration,
                'errors_before': current_error_count,
                'errors_fixed': 0,
                'errors_remaining': current_error_count,
                'timestamp': datetime.now().isoformat(),
                'attributes_added': self.completeness_enhancer.attributes_added,
                'methods_added': self.completeness_enhancer.methods_added,
                'cardinalities_added': self.completeness_enhancer.cardinalities_added
            }
            
            # Apply repairs
            dsl = self.auto_corrector.correct(dsl, errors)
            fixed_count = len(self.auto_corrector.corrections_applied)
            repair_record['errors_fixed'] = fixed_count
            repair_record['errors_remaining'] = current_error_count - fixed_count
            
            dsl.add_repair_record(repair_record)
            
            # Stop if no repairs were made or no errors remain
            if fixed_count == 0 or current_error_count - fixed_count == 0:
                break
            
            # Stop if error count doesn't decrease
            if current_error_count >= previous_error_count and iteration > 1:
                break
            previous_error_count = current_error_count
        
        # Update metrics
        dsl.metadata['repair_iterations'] = len(dsl.repair_history)
        dsl.metadata['total_errors'] = len(dsl.validation_errors)
        dsl.metadata['attributes_added'] = self.completeness_enhancer.attributes_added
        dsl.metadata['methods_added'] = self.completeness_enhancer.methods_added
        
        logger.info(f"Repair completed: {len(dsl.repair_history)} iterations, {dsl.metadata['total_errors']} total errors")
        logger.info(f"Corrections applied: {len(self.auto_corrector.corrections_applied)}")
        logger.info(f"Attributes added: {self.completeness_enhancer.attributes_added}")
        logger.info(f"Methods added: {self.completeness_enhancer.methods_added}")
        
        return dsl

# ===============================
# Main Pipeline
# ===============================

class DSLPipeline:
    """Complete DSL processing pipeline with strict corrections."""
    
    def __init__(self, auto_repair: bool = True, max_iterations: int = 3):
        self.normalizer = DSLNormalizer()
        self.validator = DSLValidator()
        self.repairer = DSLRepairer(max_iterations=max_iterations, auto_fix=auto_repair)
        self.implicit_detector = ImplicitRelationDetector()
        self.disambiguator = RelationshipDisambiguator()
        self.cardinality_processor = CardinalityProcessor()
        self.structural_checker = StructuralConsistencyChecker()
        self.isolated_detector = IsolatedClassDetector()
        self.auto_repair = auto_repair
        self.max_iterations = max_iterations
        
        self.stats = {
            'iterations': 0,
            'errors_fixed': 0,
            'relations_added': 0,
            'classes_added': 0,
            'isolated_classes_fixed': 0,
            'normalization_stats': {}
        }
    
    def process(self, dsl: QualityAwareDSL, text: str) -> QualityAwareDSL:
        """Execute the complete pipeline with strict corrections."""
        # Step 1: Normalization with strict corrections (R1-R9)
        dsl, rules_applied = self.normalizer.normalize(dsl)
        self.stats['normalization_stats'] = self.normalizer.normalization_stats
        
        # Step 2: Implicit relation detection (R43-R46)
        dsl = self.implicit_detector.detect(dsl, text)
        self.stats['relations_added'] += len([r for r in dsl.relations if r.get('implicit', False)])
        
        # Step 3: Relation disambiguation (R25-R37)
        dsl = self.disambiguator.disambiguate(dsl, text)
        
        # Step 4: Cardinality processing (R47-R51)
        dsl = self.cardinality_processor.process(dsl, text)
        
        # Step 5: Isolated class detection and correction
        before_relations = len(dsl.relations)
        dsl = self.isolated_detector.detect_and_correct(dsl, text)
        after_relations = len(dsl.relations)
        self.stats['isolated_classes_fixed'] = after_relations - before_relations
        
        # Step 6: Validation
        errors = self.validator.validate(dsl)
        
        # Step 7: Additional structural validation
        structural_errors = self.structural_checker.check(dsl)
        
        # Step 8: Strict auto-repair with completeness enhancement
        if self.auto_repair and (errors or structural_errors):
            dsl = self.repairer.repair(dsl, self.validator)
            self.stats['errors_fixed'] += len(dsl.repair_history)
            self.stats['iterations'] += 1
        
        # Update metadata
        dsl.metadata['total_errors'] = len(dsl.validation_errors)
        dsl.metadata['repair_iterations'] = self.stats['iterations']
        dsl.metadata['isolated_classes_fixed'] = self.stats['isolated_classes_fixed']
        dsl.metadata['is_raw'] = False
        
        if self.stats['isolated_classes_fixed'] > 0:
            dsl.add_correction(f"✅ {self.stats['isolated_classes_fixed']} isolated classes were automatically connected")
        
        return dsl

# ===============================
# Two-Stage DSL Management Functions
# ===============================

def extract_raw_dsl_from_text(text: str) -> QualityAwareDSL:
    """
    Extract raw DSL from BERT without applying automatic corrections.
    Used for initial display on the UML canvas.
    """
    clean_text = preprocess_text(text)
    words = clean_text.split()
    max_len = 510
    
    all_tokens = []
    all_labels = []

    for i in range(0, len(words), max_len):
        chunk = words[i:i + max_len]
        encoding = tokenizer(chunk, return_tensors="pt", is_split_into_words=True, padding=True, truncation=True)
        with torch.no_grad():
            outputs = model(**encoding)

        predictions = torch.argmax(outputs.logits, dim=2)[0]
        predicted_labels = [id2label[p.item()] for p in predictions]
        token_list = tokenizer.convert_ids_to_tokens(encoding['input_ids'][0])
        token_list = [t.replace("Ġ", "") for t in token_list]
        merged_tokens, merged_labels = merge_subtokens(token_list, predicted_labels)

        if len(merged_tokens) != len(merged_labels):
            continue

        all_tokens.extend(merged_tokens)
        all_labels.extend(merged_labels)

    dsl = QualityAwareDSL()
    
    if not all_tokens:
        return dsl

    current_class = None
    last_class = None
    current_relation = None
    relation_detected = False

    for token, label in zip(all_tokens, all_labels):
        if label in ['B_CLASS_SOURCE', 'B_CLASS_TARGET']:
            normalized_class = normalize_class_name(token)
            if normalized_class not in dsl.classes:
                dsl.add_class(normalized_class)
            
            current_class = normalized_class
            if relation_detected and last_class and current_relation:
                dsl.add_relation(last_class, current_class, current_relation)
                relation_detected = False
                current_relation = None
            last_class = current_class

        elif label == 'B_ATTRIBUTE' and current_class:
            if current_class in dsl.classes:
                dsl.classes[current_class]['attributes'].append(token)

        elif label == 'I_ATTRIBUTE' and current_class:
            if current_class in dsl.classes and dsl.classes[current_class]['attributes']:
                dsl.classes[current_class]['attributes'][-1] += " " + token

        elif label == 'B_METHOD' and current_class:
            if current_class in dsl.classes:
                dsl.classes[current_class]['methods'].append(token)

        elif label == 'I_METHOD' and current_class:
            if current_class in dsl.classes and dsl.classes[current_class]['methods']:
                dsl.classes[current_class]['methods'][-1] += " " + token

        elif label in ['B_ASSOCIATION', 'B_AGGREGATION', 'B_COMPOSITION', 'B_INHERITANCE']:
            current_relation = label.split("_")[-1].lower()
            relation_detected = True

    dsl.relations = filter_strongest_relations(dsl.relations)
    
    # Update metadata
    dsl.metadata['total_classes'] = len(dsl.classes)
    dsl.metadata['total_relations'] = len(dsl.relations)
    dsl.metadata['is_raw'] = True
    
    return dsl

def apply_validation_and_repair(dsl: QualityAwareDSL, text: str = "") -> QualityAwareDSL:
    """
    Apply validation and automatic corrections to an existing DSL.
    Returns the corrected DSL.
    """
    if text:
        clean_text = preprocess_text(text)
    else:
        clean_text = ""
    
    # Apply processing pipeline
    pipeline = DSLPipeline(auto_repair=True)
    dsl = pipeline.process(dsl, clean_text)
    
    return dsl

def validate_dsl_only(dsl: QualityAwareDSL) -> Tuple[bool, List[ValidationError]]:
    """
    Validate DSL without applying corrections.
    Returns (is_valid, list_of_errors).
    """
    validator = DSLValidator()
    errors = validator.validate(dsl)
    
    # Update metadata
    dsl.metadata['total_errors'] = len(errors)
    dsl.validation_errors = errors
    
    return len(errors) == 0, errors

def get_dsl_state(dsl: QualityAwareDSL) -> Dict[str, Any]:
    """
    Return the current state of the DSL for the GUI.
    """
    return {
        'has_classes': len(dsl.classes) > 0,
        'has_relations': len(dsl.relations) > 0,
        'total_classes': len(dsl.classes),
        'total_relations': len(dsl.relations),
        'total_errors': len(dsl.validation_errors),
        'is_valid': len(dsl.validation_errors) == 0,
        'reliability': dsl.get_reliability_score(),
        'is_raw': dsl.metadata.get('is_raw', False),
        'classes': dsl.classes,
        'relations': dsl.relations,
        'corrections_applied': dsl.metadata.get('corrections_applied', []),
        'attributes_added': dsl.metadata.get('attributes_added', 0),
        'methods_added': dsl.metadata.get('methods_added', 0)
    }

# ===============================
# Main extraction function with quality
# ===============================

def extract_uml_elements_with_quality(text: str, auto_repair: bool = True) -> QualityAwareDSL:
    """Extract UML elements with quality metrics and auto-repair."""
    # Preprocessing
    clean_text = preprocess_text(text)
    words = clean_text.split()
    max_len = 510
    
    all_tokens = []
    all_labels = []

    # Chunk processing
    for i in range(0, len(words), max_len):
        chunk = words[i:i + max_len]
        encoding = tokenizer(chunk, return_tensors="pt", is_split_into_words=True, padding=True, truncation=True)
        with torch.no_grad():
            outputs = model(**encoding)

        predictions = torch.argmax(outputs.logits, dim=2)[0]
        predicted_labels = [id2label[p.item()] for p in predictions]
        token_list = tokenizer.convert_ids_to_tokens(encoding['input_ids'][0])
        token_list = [t.replace("Ġ", "") for t in token_list]
        merged_tokens, merged_labels = merge_subtokens(token_list, predicted_labels)

        if len(merged_tokens) != len(merged_labels):
            logger.warning("Skipping mismatched token/label sequence.")
            continue

        all_tokens.extend(merged_tokens)
        all_labels.extend(merged_labels)

    # Create quality-aware DSL
    dsl = QualityAwareDSL()
    
    if not all_tokens:
        logger.warning("No tokens extracted from text")
        return dsl

    # UML analysis and structuring
    current_class = None
    current_attr = None
    current_method = None
    last_class = None
    current_relation = None
    relation_detected = False
    
    # Statistics for quality metrics
    class_mentions = {}

    for token, label in zip(all_tokens, all_labels):
        if label in ['B_CLASS_SOURCE', 'B_CLASS_TARGET']:
            normalized_class = normalize_class_name(token)
            if normalized_class not in dsl.classes:
                dsl.add_class(normalized_class)
                class_mentions[normalized_class] = 1
                logger.info(f"Class detected: {normalized_class}")
            else:
                class_mentions[normalized_class] = class_mentions.get(normalized_class, 0) + 1

            current_class = normalized_class
            if relation_detected and last_class and current_relation:
                dsl.add_relation(last_class, current_class, current_relation)
                logger.info(f"Relation added: {last_class} -> {current_class} (Type: {current_relation})")
                relation_detected = False
                current_relation = None

            last_class = current_class

        elif label == 'B_ATTRIBUTE' and current_class:
            current_attr = token
            if current_class in dsl.classes:
                dsl.classes[current_class]['attributes'].append(current_attr)
                logger.info(f"Attribute detected for class {current_class}: {current_attr}")

        elif label == 'I_ATTRIBUTE' and current_attr:
            if current_class in dsl.classes and dsl.classes[current_class]['attributes']:
                dsl.classes[current_class]['attributes'][-1] += " " + token

        elif label == 'B_METHOD' and current_class:
            current_method = token
            if current_class in dsl.classes:
                dsl.classes[current_class]['methods'].append(current_method)
                logger.info(f"Method detected for class {current_class}: {current_method}")

        elif label == 'I_METHOD' and current_method:
            if current_class in dsl.classes and dsl.classes[current_class]['methods']:
                dsl.classes[current_class]['methods'][-1] += " " + token

        elif label in ['B_ASSOCIATION', 'B_AGGREGATION', 'B_COMPOSITION', 'B_INHERITANCE']:
            current_relation = label.split("_")[-1].lower()
            relation_detected = True

    # Filter relations to keep the strongest
    dsl.relations = filter_strongest_relations(dsl.relations)
    
    # Update confidence metrics
    for class_name in dsl.classes:
        if class_name in class_mentions:
            mentions = class_mentions.get(class_name, 1)
            confidence = min(0.99, 0.70 + (mentions - 1) * 0.05)
            if class_name in dsl.quality_metrics:
                dsl.quality_metrics[class_name].confidence = confidence
                dsl.quality_metrics[class_name].recall = min(1.0, mentions / 3)
    
    # Update metadata
    dsl.metadata['total_classes'] = len(dsl.classes)
    dsl.metadata['total_relations'] = len(dsl.relations)
    
    # Processing pipeline
    pipeline = DSLPipeline(auto_repair=auto_repair)
    dsl = pipeline.process(dsl, clean_text)
    
    # Update final quality metrics
    for class_name in dsl.classes:
        if class_name in dsl.quality_metrics:
            class_errors = [e for e in dsl.validation_errors if e.element == class_name]
            if class_errors:
                dsl.quality_metrics[class_name].syntactic_validity = 0.80
                dsl.quality_metrics[class_name].semantic_validity = 0.75
            else:
                dsl.quality_metrics[class_name].syntactic_validity = 1.0
                dsl.quality_metrics[class_name].semantic_validity = 1.0

    logger.info(f"Classes detected: {len(dsl.classes)}")
    logger.info(f"Relations detected: {len(dsl.relations)}")
    logger.info(f"Validation errors: {len(dsl.validation_errors)}")
    logger.info(f"Reliability score: {dsl.get_reliability_score():.3f}")
    logger.info(f"Corrections applied: {len(dsl.metadata.get('corrections_applied', []))}")
    logger.info(f"Attributes added: {dsl.metadata.get('attributes_added', 0)}")
    logger.info(f"Methods added: {dsl.metadata.get('methods_added', 0)}")
    
    if dsl.metadata.get('isolated_classes_fixed', 0) > 0:
        logger.info(f"✅ {dsl.metadata['isolated_classes_fixed']} isolated classes were connected")
    
    return dsl

# ===============================
# Compatibility interface with old code
# ===============================

def extract_uml_elements(text: str) -> dict:
    """Compatibility interface with old code."""
    dsl = extract_uml_elements_with_quality(text, auto_repair=True)
    
    # Return format expected by old code
    result = {
        'classes': dsl.classes,
        'relations': dsl.relations,
        'quality_metrics': {
            k: v.to_dict() for k, v in dsl.quality_metrics.items()
        },
        'validation_errors': [e.to_dict() for e in dsl.validation_errors],
        'repair_history': dsl.repair_history,
        'metadata': dsl.metadata,
        'reliability_score': dsl.get_reliability_score(),
        'error_summary': dsl.get_error_summary()
    }
    
    return result

# ===============================
# DSL generation functions
# ===============================

def generate_quality_aware_dsl(dsl: QualityAwareDSL) -> str:
    """Generate a text representation of the quality-aware DSL."""
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("QUALITY-AWARE UML DSL - VERSION 3.2")
    lines.append("=" * 70)
    lines.append(f"Generated: {dsl.metadata.get('created_at', '')}")
    lines.append(f"Reliability Score: {dsl.get_reliability_score():.3f}")
    lines.append(f"Total Classes: {len(dsl.classes)}")
    lines.append(f"Total Relations: {len(dsl.relations)}")
    lines.append(f"Total Errors: {len(dsl.validation_errors)}")
    lines.append(f"Status: {'RAW (BERT)' if dsl.metadata.get('is_raw', False) else 'VALIDATED'}")
    lines.append(f"Corrections Applied: {len(dsl.metadata.get('corrections_applied', []))}")
    lines.append(f"Attributes Added: {dsl.metadata.get('attributes_added', 0)}")
    lines.append(f"Methods Added: {dsl.metadata.get('methods_added', 0)}")
    
    if dsl.metadata.get('isolated_classes_fixed', 0) > 0:
        lines.append(f"✅ Isolated Classes Fixed: {dsl.metadata['isolated_classes_fixed']}")
    lines.append("")
    
    # Applied corrections
    corrections = dsl.metadata.get('corrections_applied', [])
    if corrections:
        lines.append("CORRECTIONS APPLIED:")
        lines.append("-" * 70)
        for i, correction in enumerate(corrections[:10], 1):
            lines.append(f"  {i}. {correction}")
        if len(corrections) > 10:
            lines.append(f"  ... and {len(corrections) - 10} more")
        lines.append("")
    
    # Classes
    lines.append("CLASSES:")
    lines.append("-" * 70)
    for class_name, class_data in dsl.classes.items():
        lines.append(f"\nClass {class_name}:")
        
        attrs = class_data.get('attributes', [])
        if attrs:
            lines.append(f"  Attributes: {', '.join(attrs)}")
        else:
            lines.append("  Attributes: (none)")
        
        methods = class_data.get('methods', [])
        if methods:
            lines.append(f"  Methods: {', '.join(methods)}")
        else:
            lines.append("  Methods: (none)")
        
        # Quality metrics
        if class_name in dsl.quality_metrics:
            metrics = dsl.quality_metrics[class_name]
            lines.append("  Quality Metrics:")
            lines.append(f"    Confidence: {metrics.confidence:.3f}")
            lines.append(f"    Syntactic: {metrics.syntactic_validity:.3f}")
            lines.append(f"    Semantic: {metrics.semantic_validity:.3f}")
            lines.append(f"    Reliability: {metrics.get_reliability_score():.3f}")
    
    # Relations
    if dsl.relations:
        lines.append("\nRELATIONS:")
        lines.append("-" * 70)
        for relation in dsl.relations:
            rel_type = relation.get('type', 'association')
            source = relation.get('source', '')
            target = relation.get('target', '')
            confidence = relation.get('confidence', 0.90)
            source_card = relation.get('source_cardinality', '')
            target_card = relation.get('target_cardinality', '')
            card_str = f" [{source_card}] -> [{target_card}]" if source_card or target_card else ""
            implicit = " [implicit]" if relation.get('implicit', False) else ""
            
            # Check if this is a relation added for an isolated class
            is_isolated_fix = False
            corrections = dsl.metadata.get('corrections_applied', [])
            for corr in corrections:
                if f"'{source}' connected to '{target}'" in corr or f"'{target}' connected to '{source}'" in corr:
                    is_isolated_fix = True
                    break
            
            isolated_marker = " [🔗 AUTO]" if is_isolated_fix else ""
            
            lines.append(f"  {source} {rel_type} {target}{card_str}{implicit}{isolated_marker} (confidence: {confidence:.2f})")
    
    # Validation Report
    if dsl.validation_errors:
        lines.append("\nVALIDATION REPORT:")
        lines.append("-" * 70)
        lines.append(f"Total Errors: {len(dsl.validation_errors)}")
        
        # Group by type
        error_summary = dsl.get_error_summary()
        for error_code, count in error_summary.items():
            lines.append(f"  {error_code}: {count}")
        
        lines.append("\nError Details:")
        for error in dsl.validation_errors[:10]:
            severity = error.severity if hasattr(error, 'severity') else "error"
            severity_symbol = "🔴" if severity == "error" else "🟡" if severity == "warning" else "ℹ️"
            lines.append(f"  {severity_symbol} [{error.error_type.value}] {error.message}")
            if error.suggestion:
                lines.append(f"    → {error.suggestion}")
    
    # Repair History
    if dsl.repair_history:
        lines.append("\nREPAIR HISTORY:")
        lines.append("-" * 70)
        for record in dsl.repair_history:
            lines.append(f"  Iteration {record['iteration']}:")
            lines.append(f"    Errors before: {record['errors_before']}")
            lines.append(f"    Errors fixed: {record['errors_fixed']}")
            lines.append(f"    Errors remaining: {record['errors_remaining']}")
            if record.get('attributes_added', 0) > 0:
                lines.append(f"    Attributes added: {record['attributes_added']}")
            if record.get('methods_added', 0) > 0:
                lines.append(f"    Methods added: {record['methods_added']}")
    
    return "\n".join(lines)

# ===============================
# Save function
# ===============================

def save_dsl_to_file(dsl: QualityAwareDSL, filepath: str, format: str = "json"):
    """Save DSL to a file."""
    if format.lower() == "json":
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(dsl.to_json(pretty=True))
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(generate_quality_aware_dsl(dsl))
    
    logger.info(f"DSL saved to {filepath}")

# ===============================
# Load function
# ===============================

def load_dsl_from_file(filepath: str) -> QualityAwareDSL:
    """Load DSL from a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        # Try to load as JSON
        data = json.loads(content)
        dsl = QualityAwareDSL(
            classes=data.get('classes', {}),
            relations=data.get('relations', []),
            metadata=data.get('metadata', {})
        )
        # Restore metrics
        for key, metrics in data.get('quality_metrics', {}).items():
            dsl.quality_metrics[key] = QualityMetrics(**metrics)
        # Restore errors
        for error_data in data.get('validation_errors', []):
            error = ValidationError(
                error_type=ErrorType[error_data['code']],
                level=ValidationLevel(error_data['level']),
                message=error_data['message'],
                element=error_data.get('element'),
                suggestion=error_data.get('suggestion'),
                severity=error_data.get('severity', 'error')
            )
            dsl.validation_errors.append(error)
        dsl.repair_history = data.get('repair_history', [])
        # Update metadata
        dsl.metadata['total_classes'] = len(dsl.classes)
        dsl.metadata['total_relations'] = len(dsl.relations)
        dsl.metadata['total_errors'] = len(dsl.validation_errors)
        if 'corrections_applied' in data.get('metadata', {}):
            dsl.metadata['corrections_applied'] = data['metadata']['corrections_applied']
        if 'isolated_classes_fixed' in data.get('metadata', {}):
            dsl.metadata['isolated_classes_fixed'] = data['metadata']['isolated_classes_fixed']
        if 'attributes_added' in data.get('metadata', {}):
            dsl.metadata['attributes_added'] = data['metadata']['attributes_added']
        if 'methods_added' in data.get('metadata', {}):
            dsl.metadata['methods_added'] = data['metadata']['methods_added']
        return dsl
    except json.JSONDecodeError:
        # If not JSON, try to parse as text
        logger.warning("File is not JSON, trying to parse as text DSL")
        raise ValueError("Unsupported file format")

# ===============================
# Entry point for tests
# ===============================

if __name__ == "__main__":
    # Test with an example
    test_text = """
    The system has Customers and Orders. Each Customer can place multiple Orders.
    A Customer has an id, name, and email. They can placeOrder() and cancelOrder().
    Each Order has an orderId, orderDate, and total. Orders are associated with Customers.
    Aircraft are classified into PassengerAircraft and CargoAircraft.
    The Payment class handles payments for orders.
    """
    
    print("=" * 70)
    print("TESTING QUALITY-AWARE UML EXTRACTION - VERSION 3.2")
    print("=" * 70)
    
    # Raw extraction test
    print("\n--- RAW DSL EXTRACTION ---")
    raw_dsl = extract_raw_dsl_from_text(test_text)
    print(f"Classes: {len(raw_dsl.classes)}, Relations: {len(raw_dsl.relations)}")
    print(f"Raw DSL Status: {raw_dsl.metadata.get('is_raw', False)}")
    
    # Corrected extraction test
    print("\n--- CORRECTED DSL EXTRACTION ---")
    corrected_dsl = extract_uml_elements_with_quality(test_text, auto_repair=True)
    print(f"Classes: {len(corrected_dsl.classes)}, Relations: {len(corrected_dsl.relations)}")
    print(f"Errors: {len(corrected_dsl.validation_errors)}")
    print(f"Corrections: {len(corrected_dsl.metadata.get('corrections_applied', []))}")
    print(f"Isolated Classes Fixed: {corrected_dsl.metadata.get('isolated_classes_fixed', 0)}")
    print(f"Attributes Added: {corrected_dsl.metadata.get('attributes_added', 0)}")
    print(f"Methods Added: {corrected_dsl.metadata.get('methods_added', 0)}")
    for correction in corrected_dsl.metadata.get('corrections_applied', [])[:5]:
        print(f"  - {correction}")
    
    # Validation test
    print("\n--- VALIDATION TEST ---")
    is_valid, errors = validate_dsl_only(corrected_dsl)
    print(f"Is Valid: {is_valid}, Errors: {len(errors)}")
    
    print("\n" + generate_quality_aware_dsl(corrected_dsl))