# LinkML Schema

## 1. What is LinkML?

**LinkML (Linked Data Modeling Language)** is a schema language for defining the structure and meaning of data.

Generally, the data model is defined in a YAML schema, and LinkML can use that schema to generate or work with things such as:

- Data validators
- JSON Schema
- RDF/OWL representations
- Python classes

The core idea is:

> **Define the structure and semantics of your data once, then use that schema to validate and generate different representations of the data.**

Conceptually:

```
                LinkML Schema
                     ↓
             Defines structure
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
        JSON       RDF        Python
        data      triples      classes
```

The schema is therefore the **model**, while JSON/YAML/RDF/etc. contain instances of that model.


## 2. LinkML Syntax

If you are familiar with general data schema, some keywords in LinkML can be thought of as:

| LinkML Semantics  | Generic Schema  | Syntax/Keywords | Examples | 
|-------------------|----------------------|-------|------------- |
| Classes  |  objects/entities |  `classes` | [line 17, relations](./relations.yaml)
| Slots/Attributes | properties/fields of objects  | `attributes` / `slots` | [line 30, objects](./objects.yaml) 
| Types  | property types  | `range` | self-defined classes as types, [Provenance in common](./common.yaml)
| Enums  | categorical values  | `enums` | this enum definiton: [weather](./weather.yaml) is used in [line 145, objects](./objects.yaml)
| Inheritance  |  relationships btw types of entities  | `is_a` | [line 41, relations](./relations.yaml) 

Note: the `id, name, version, description, imports` are metadata one can attach to a LinkML model

---

### 2.1 Abstract Classes
---
Notice in [relations](./relations.yaml), the class `Relation` is an abstract class
```yaml
Relation:
    description: An abstract relation between two objects in the scene graph.
    abstract: true
    attributes:
```
Similar to abstract classes in Java, they are meant to capture common properties of their subclasses, and not intended to be instantiated directly. Example subclasses: `SpatialRelation` and `RoadObjectRelation`
```yaml
SpatialRelation:
    abstract: true
    is_a: Relation
```
They inherit the same attributes and structure `Relation` has

#### 2.1.1 Top-level Entry

In [scene_graph](./scene_graph.yaml), one can see class Scene has the construct `tree_root: true`, this is telling LinkML that `Scene` can be reached by rest of the schema's data structure. So when LinkML tools serialize, validate, or otherwise process the object graph, `Scene` is identified as the top-level class.

---

### 2.2 Difference Between Slots and Attributes

---

`attributes` are just **inline slots**, in other words, they're essentially a slot that is declared locally within the class.

However, slots are declared **globally** under the top-level `slots` section. Global slots can then be reused by multiple classes, which is useful when the same property/relationship is shared across different classes.

For example:

```yaml
slots:
  id:
    range: string

  timestamp:
    range: float

classes:
  Frame:
    slots:
      - id
      - timestamp

  Scene:
    slots:
      - id
```

Here, `id` and `timestamp` are globally defined slots, and classes reference them through their `slots` list.

This also allows a slot to be **customized for a particular class** using `slot_usage`. This is especially useful when a class inherits a slot from a parent class but needs to impose additional constraints or change how that slot behaves for the child class.

For example:

```yaml
slots:
  id:
    range: string

classes:
  RoadUser:
    slots:
      - id

  EgoVehicle:
    is_a: RoadUser
    slot_usage:
      id:
        equals_string: ego
```

`EgoVehicle` inherits the `id` slot from `RoadUser`, but `slot_usage:` specifies that, **within `EgoVehicle`**, the inherited `id` slot must have the value `"ego"`.

> <font color="red">Important</font>: 
`slot_usage` doesn't only apply to global slots, it can also be used in inline slots when inheritance, an equivalent definition is found in [line 63, objects](./objects.yaml). You can see the field `id` is only identified inline.

---

### 2.3 Constructs of Attributes/Slots
---
In the table summarizing LinkML Syntax, the only construct for attributes is `range`, but one could define a lot more, some examples are:

| Attribute Construct  | Explanation  | Examples | 
|-------------------|----------------------|------------- |
| `minimum_value`  | self-explanatory | [line 43, common](./common.yaml)
| `maximum_value`  | self-explanatory | ---
| `required` | boolean, self-explanatory  | [line 44, common](./common.yaml)
| `multivalued`  | boolean, array attributes  | [line 35, relationships](./relationships.yaml), another good example is `frames` in JSON we generated before
| `inlined_as_list`  | boolean, stating whether the list objects should be written directly as list under the field, find more details in the section below  | [scene_graph](./scene_graph.yaml)
| `identifier`  | boolean; marks the attribute as an identifier for instances of the class | ---
| `pattern`  | regular expression to match strings of pattern | ---

---

#### 2.3.1 Inline as List
Essentially, it's just a styling choice for LinkML:
```
inlined_as_list: true
        ↓
Scene
 └── frames
      ├── {full Frame object}
      ├── {full Frame object}
      └── {full Frame object}


inlined_as_list: false
        ↓
Scene
 └── frames
      ├── frame_001 ──→ Frame object defined elsewhere
      ├── frame_002 ──→ Frame object defined elsewhere
      └── frame_003 ──→ Frame object defined elsewhere
```

---

## 3. Resources
| Links  | Description  |
|-------------------|----------------------|
| [LinkML schema documentation](https://linkml.io/linkml/schemas/)  | Official Documentation |
| [LinkML: Slots](https://linkml.io/linkml/schemas/slots.html)  | Official Documentation on LinkML Slots |
| [LinkML Schema Automator](https://linkml.io/schema-automator/) | A toolkit for bootstrapping schemas, could infer an initial schema from a dataset |