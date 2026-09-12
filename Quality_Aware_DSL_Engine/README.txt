__________________________________________________________________________________
README — Reliability-Aware DSL Pipeline for UML Class Model and Code Generation
__________________________________________________________________________________
1. OVERVIEW

This project implements a reliability-aware pipeline for automatically
generating UML class models from textual software specifications.

The pipeline uses a fine-tuned BERT model for UML concept extraction and
a Domain-Specific Language (DSL) as an intermediate representation. The
DSL acts as a pivot representation between natural-language
specifications and the final UML model.

The main objective is to improve the reliability, structural
consistency, semantic coherence, and self-repair capability of
automatically generated UML class models.

2. MAIN COMPONENTS

2.1 Textual Specification

The input is a natural-language software specification describing the
functional and structural characteristics of a system.

The specification may contain:

-   Classes and domain concepts
-   Attributes
-   Operations or methods
-   Associations
-   Aggregations
-   Compositions
-   Inheritance relationships
-   Multiplicities
-   Implicit or contextual relationships

2.2 Fine-Tuned BERT Extraction

A fine-tuned BERT model performs token-level classification to identify
UML concepts and relations in the textual specification.

The extraction layer identifies elements such as:

-   Class names
-   Attributes
-   Methods
-   Source classes
-   Target classes
-   Relations
-   Other UML-related concepts

The output of this stage is transformed into the intermediate DSL.

2.3 DSL Intermediate Representation

The DSL provides a structured and explicit representation of the
extracted model.

A simplified class structure is:

Class Customer: Attributes: customerId name emailAddress Methods:
browseProducts() placeOrder()

A relation can be represented as:

Relation: Customer association Order

The DSL is used as a pivot between natural language and UML. This makes
it possible to inspect, normalize, validate, repair, and transform the
model before UML generation.

3. DSL NORMALIZATION

Normalization is applied before validation.

The normalization rules are organized into five main groups:

-   Structural normalization
-   Lexical normalization
-   Attribute normalization
-   Method normalization
-   Relation normalization

The normalization stage handles, among other things:

-   Duplicate classes
-   Duplicate attributes
-   Duplicate methods
-   Invalid or inconsistent names
-   Lexical variants
-   Incorrect element placement
-   Orphan elements
-   Relation type variants
-   Inconsistent inheritance orientation
-   Duplicate relations
-   Cardinality preservation

Normalization aims to produce a homogeneous DSL representation without
changing the intended meaning of the specification.

4. DSL VALIDATION

Validation is performed at two levels.

4.1 Syntax Validation

Syntax validation checks whether the DSL conforms to its structural and
formatting rules.

Typical checks include:

-   Presence of the Class keyword
-   Valid class names
-   Valid class structure
-   Valid Attributes and Methods sections
-   Valid attribute names
-   Valid method names
-   Method notation ()
-   Valid relation structure
-   Valid source and target endpoints
-   Valid relation types
-   Valid cardinality syntax
-   Detection of duplicated elements

4.2 Semantic Validation

Semantic validation verifies whether the DSL is coherent with the
meaning of the original specification.

Typical checks include:

-   Relevance of classes
-   Class justification
-   Correct ownership of attributes
-   Correct ownership of methods
-   Distinction between attributes and behaviors
-   Correct interpretation of relations
-   Association versus aggregation versus composition
-   Correct inheritance orientation
-   Preservation of implicit but strongly justified relations
-   Consistency with the global specification context

5. RELATION DISAMBIGUATION

The pipeline includes a dedicated disambiguation mechanism for UML
relationships.

The main relation types considered are:

-   Association
-   Aggregation
-   Composition
-   Inheritance

The decision process relies primarily on explicit information from the
specification, followed by semantic evidence and contextual information.

Examples:

-   uses / interacts with / works with -> Association
-   whole-part with independent lifetime -> Aggregation
-   strong lifecycle dependency -> Composition
-   is a type of / subtype of -> Inheritance

When the available evidence is insufficient, the system does not perform
an arbitrary correction. Instead, it reports the ambiguity.

6. MULTIPLICITY INTERPRETATION

The pipeline extracts multiplicities from explicit linguistic
indicators.

Examples include:

-   one -> 1
-   exactly one -> 1
-   a single -> 1
-   zero or one -> 0..1
-   one or more -> 1..*
-   at least one -> 1..*
-   many -> 0..* or 1..*, depending on context
-   zero or more -> 0..*

Contextual rules are also used for expressions such as:

-   Each X has one Y
-   Each X has many Y
-   Each X contains one or more Y
-   Each X is associated with exactly one Y

If the specification does not provide sufficient information, the
multiplicity remains unspecified rather than being arbitrarily inferred.

7. CONFLICT RESOLUTION

Conflicts can arise when several extracted elements or relations
represent different interpretations of the same textual information.

The conflict-resolution stage handles cases such as:

-   Duplicate classes
-   Duplicate attributes
-   Duplicate methods
-   Orphan elements
-   Invalid references
-   Contradictory relations
-   Reversed inheritance
-   Incompatible cardinalities
-   Incorrect element ownership
-   Lexically equivalent concepts

For semantic conflicts, the system prioritizes the strongest available
evidence and preserves ambiguity when no reliable decision can be made.

8. SELF-REPAIR

The self-repair engine applies only corrections that are sufficiently
justified.

Typical repair operations include:

-   Merging duplicate classes
-   Removing duplicated attributes or methods
-   Reassigning orphan elements when ownership is identifiable
-   Normalizing names
-   Converting an action represented as an attribute into a method
-   Correcting relation orientation
-   Replacing an association with aggregation or composition when
    justified
-   Correcting multiplicities when textual evidence is unambiguous
-   Adding strongly justified implicit relations

The system avoids speculative repairs. When there is insufficient
evidence, the anomaly is reported without automatic modification.

9. INFORMATION PRIORITY

The decision process follows an information-priority hierarchy:

1.  Explicit information from the specification
2.  Strongly justified semantic relations
3.  DSL syntax and structural information
4.  Global specification context
5.  UML constraints
6.  DSL normalization rules
7.  Insufficiently justified hypotheses

The last category is not used for automatic correction.

10. UML GENERATION

After normalization, validation, disambiguation, and repair, the
validated DSL is transformed into a UML class model.

The UML representation may be generated using PlantUML or another UML
serialization mechanism.

The resulting model contains:

-   Classes
-   Attributes
-   Methods
-   Associations
-   Aggregations
-   Compositions
-   Inheritance
-   Multiplicities

11. CODE GENERATION

The validated UML model can subsequently be transformed into source
code.

The pipeline supports code generation for target languages such as:

-   Python
-   Java
-   C#

The code-generation stage relies on the validated UML model rather than
directly transforming the original textual specification.

12. ERROR CATEGORIES

The system distinguishes several classes of errors.

Syntax errors include:

-   Missing class
-   Invalid name
-   Missing section
-   Invalid attribute
-   Invalid method
-   Incomplete relation
-   Unknown relation
-   Invalid endpoint
-   Duplication
-   Malformed cardinality
-   Missing attribute
-   Missing method

Semantic errors include:

-   Irrelevant class
-   Incorrect ownership
-   Attribute/behavior confusion
-   Incorrect relation type
-   Incorrect inheritance orientation
-   Missing justified relation
-   Contradictory relations
-   Incorrect multiplicity
-   Insufficient semantic justification

13. MAIN PROCESSING LOGIC

The conceptual processing sequence is:

1.  Read the textual specification.

2.  Extract UML-related concepts using the fine-tuned BERT model.

3.  Build the intermediate DSL.

4.  Normalize the DSL.

5.  Validate its syntax.

6.  Validate its semantics.

7.  Detect ambiguities and conflicts.

8.  Resolve relations and multiplicities when justified.

9.  Apply safe self-repair operations.

10. Revalidate the repaired DSL.

11. Generate the UML class model.

12. Generate source code from the validated UML model.

13. Record errors, corrections, and evaluation results.

14. RELIABILITY PRINCIPLE

The DSL is not only a data-exchange format. It acts as a reliability
mechanism.

It provides an intermediate layer where the generated model can be:

-   inspected,
-   normalized,
-   validated,
-   disambiguated,
-   repaired,
-   and traced before UML and code generation.

This separation reduces the propagation of extraction errors toward the
final UML model and generated source code.

15. PROJECT STRUCTURE

A possible project organization is:

project/ | +– data_input/ | +– specifications | +– dsl_output/ | +–
generated DSL files | +– uml_output/ | +– UML / PlantUML files | +–
generated_code/ | +– Python | +– Java | +– C# | +– logs/ | +– validation
logs | +– repair logs | +– train_bert.py +– uml_extract.py +–
llm_prompt_engine.py +– uml_visualizer.py +– uml_to_code.py +–
evaluation.py +– pipeline_manager.py +– README.txt

16. EVALUATION

The pipeline can be evaluated by comparing the extracted and generated
models with reference annotations.

Relevant measures include:

-   Syntactic accuracy
-   Structural coherence
-   Semantic adequacy
-   UML Precision
-   UML Recall
-   UML F1-score
-   Code accuracy
-   Code coherence
-   Processing latency
-   Number of detected errors
-   Number of automatically repaired errors
-   Repair success rate

A useful experimental organization is to compare the system before and
after the reliability-aware DSL mechanisms.

17. SUMMARY

The proposed pipeline follows the transformation:

Natural Language Specification -> Fine-Tuned BERT Extraction ->
Intermediate DSL -> Normalization -> Syntax Validation -> Semantic
Validation -> Disambiguation -> Conflict Resolution -> Self-Repair ->
Validated UML Model -> Source Code

The DSL therefore serves as a controlled pivot representation that
separates concept extraction from model generation and provides explicit
mechanisms for quality assurance and self-repair.
