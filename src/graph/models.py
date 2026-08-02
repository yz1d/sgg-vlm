from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.11.0"
version = "0.1.0"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'sggvlm',
     'default_range': 'string',
     'description': 'The normalized scene graph produced by sgg-vlm. The schema '
                    'contains road users, road regions, object states, and '
                    'relationships supported by the pipeline.',
     'id': 'https://w3id.org/sgg-vlm/schema',
     'imports': ['linkml:types',
                 'common',
                 'states',
                 'road_users',
                 'road_regions',
                 'relationships'],
     'name': 'sgg_vlm',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'sggvlm': {'prefix_prefix': 'sggvlm',
                             'prefix_reference': 'https://w3id.org/sgg-vlm/'}},
     'source_file': 'schema/scene_graph.yaml'} )

class RoadUserDecision(str, Enum):
    """
    A decision bundled into a perceived road-user record.
    """
    existence = "existence"
    """
    The road user exists in the scene.
    """
    classification = "classification"
    """
    The road user has the selected concrete type.
    """
    bounding_box = "bounding_box"
    """
    The road user occupies the selected image bounding box.
    """
    tracking = "tracking"
    """
    The road user has the selected cross-frame track identity.
    """


class StopArmStateValue(str, Enum):
    """
    Supported positions of a school bus's mounted stop arm.
    """
    deployed = "deployed"
    """
    The stop arm projects outward from the bus.
    """
    stowed = "stowed"
    """
    The stop arm is folded against the bus.
    """



class Provenance(ConfiguredBaseModel):
    """
    Coarse attribution for a decision represented in the scene graph.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/common'})

    source: str = Field(default=..., description="""Dataset, model, or algorithm that produced the decision.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })
    stage: str = Field(default=..., description="""Pipeline stage that added the decision to the normalized graph.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })
    model: Optional[str] = Field(default=None, description="""Exact model identifier when the source is a model.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })
    source_confidence: Optional[float] = Field(default=None, description="""Confidence reported by this source for its decision.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })


class BoundingBox2D(ConfiguredBaseModel):
    """
    An axis-aligned image-space bounding box measured in pixels.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/common'})

    x_min: float = Field(default=..., description="""Minimum horizontal pixel coordinate.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['BoundingBox2D']} })
    y_min: float = Field(default=..., description="""Minimum vertical pixel coordinate.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['BoundingBox2D']} })
    x_max: float = Field(default=..., description="""Maximum horizontal pixel coordinate.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['BoundingBox2D']} })
    y_max: float = Field(default=..., description="""Maximum vertical pixel coordinate.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['BoundingBox2D']} })


class RoadUserProvenance(Provenance):
    """
    Provenance identifying the parts of a perceived road-user record supported by a source.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    supports: list[RoadUserDecision] = Field(default=..., description="""Decisions in the road-user record supported by this source.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUserProvenance']} })
    source: str = Field(default=..., description="""Dataset, model, or algorithm that produced the decision.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })
    stage: str = Field(default=..., description="""Pipeline stage that added the decision to the normalized graph.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })
    model: Optional[str] = Field(default=None, description="""Exact model identifier when the source is a model.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })
    source_confidence: Optional[float] = Field(default=None, description="""Confidence reported by this source for its decision.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['Provenance']} })


class RoadUser(ConfiguredBaseModel):
    """
    A traffic participant represented in the scene graph.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["RoadUser"] = Field(default="RoadUser", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class EgoVehicle(RoadUser):
    """
    The observing vehicle and reference frame for spatial relationships.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users',
         'slot_usage': {'id': {'equals_string': 'ego', 'name': 'id'}}})

    provenance: list[Provenance] = Field(default=..., description="""Source establishing ego for this scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: Literal["ego"] = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship'],
         'equals_string': 'ego'} })
    type: Literal["EgoVehicle"] = Field(default="EgoVehicle", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class PerceivedRoadUser(RoadUser):
    """
    A non-ego road user localized in the input image.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["PerceivedRoadUser"] = Field(default="PerceivedRoadUser", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class Vehicle(PerceivedRoadUser):
    """
    An abstract perceived motor vehicle.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Vehicle"] = Field(default="Vehicle", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class Car(Vehicle):
    """
    A passenger car.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'car'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Car"] = Field(default="Car", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class Truck(Vehicle):
    """
    A truck.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'truck'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Truck"] = Field(default="Truck", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class Bus(Vehicle):
    """
    A passenger bus that is not necessarily a school bus.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'bus'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Bus"] = Field(default="Bus", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class SchoolBus(Bus):
    """
    A bus used to transport students.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'school bus'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["SchoolBus"] = Field(default="SchoolBus", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class Motorcycle(Vehicle):
    """
    A motorcycle.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'motorcycle'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Motorcycle"] = Field(default="Motorcycle", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class Cyclist(PerceivedRoadUser):
    """
    A person riding a bicycle.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'cyclist'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Cyclist"] = Field(default="Cyclist", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class Pedestrian(PerceivedRoadUser):
    """
    A person traveling on foot.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'pedestrian'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Pedestrian"] = Field(default="Pedestrian", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })


class ObjectState(ConfiguredBaseModel):
    """
    An abstract provenance-carrying state observed on a perceived road user.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/sgg-vlm/schema/states'})

    type: Literal["ObjectState"] = Field(default="ObjectState", description="""Concrete LinkML class of this object state.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose state is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the state assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the state assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class StopArmState(ObjectState):
    """
    An assertion about a school bus's mounted stop arm.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/states',
         'slot_usage': {'subject': {'name': 'subject', 'range': 'SchoolBus'}}})

    value: StopArmStateValue = Field(default=..., description="""Asserted stop-arm position.""", json_schema_extra = { "linkml_meta": {'domain_of': ['StopArmState']} })
    type: Literal["StopArmState"] = Field(default="StopArmState", description="""Concrete LinkML class of this object state.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose state is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the state assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the state assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class RoadRegion(ConfiguredBaseModel):
    """
    An image-derived road surface region represented in the scene graph.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-regions'})

    id: str = Field(default=..., description="""Identity used to reference this road region within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["RoadRegion"] = Field(default="RoadRegion", description="""Concrete LinkML class of this road region.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the existence and classification of this road region.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class Lane(RoadRegion):
    """
    A visible road corridor for one line of traffic, independent of its direction relative to ego.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/road-regions'})

    id: str = Field(default=..., description="""Identity used to reference this road region within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Lane"] = Field(default="Lane", description="""Concrete LinkML class of this road region.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the existence and classification of this road region.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class Intersection(RoadRegion):
    """
    A shared road region where traffic paths meet or cross.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/road-regions'})

    id: str = Field(default=..., description="""Identity used to reference this road region within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Intersection"] = Field(default="Intersection", description="""Concrete LinkML class of this road region.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the existence and classification of this road region.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class Relationship(ConfiguredBaseModel):
    """
    An abstract relationship between two entities in the scene graph.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Relationship"] = Field(default="Relationship", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class SpatialRelationship(Relationship):
    """
    An abstract road-coordinate relationship from a perceived road user to ego.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    subject: str = Field(default=..., description="""Perceived road user described relative to ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["SpatialRelationship"] = Field(default="SpatialRelationship", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class InFrontOf(SpatialRelationship):
    """
    The subject is longitudinally ahead of ego in road coordinates, regardless of the subject's facing or motion direction.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'exclusive_group': {'tag': 'exclusive_group',
                                             'value': 'longitudinal'},
                         'relation_extraction': {'tag': 'relation_extraction',
                                                 'value': 'enabled'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    subject: str = Field(default=..., description="""Perceived road user described relative to ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["InFrontOf"] = Field(default="InFrontOf", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class Behind(SpatialRelationship):
    """
    The subject is longitudinally behind ego in road coordinates, regardless of the subject's facing or motion direction.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'exclusive_group': {'tag': 'exclusive_group',
                                             'value': 'longitudinal'},
                         'relation_extraction': {'tag': 'relation_extraction',
                                                 'value': 'enabled'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    subject: str = Field(default=..., description="""Perceived road user described relative to ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Behind"] = Field(default="Behind", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class LeftOf(SpatialRelationship):
    """
    The subject is laterally left of ego relative to ego's road heading, not merely in the left half of the image.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'exclusive_group': {'tag': 'exclusive_group',
                                             'value': 'lateral'},
                         'relation_extraction': {'tag': 'relation_extraction',
                                                 'value': 'enabled'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    subject: str = Field(default=..., description="""Perceived road user described relative to ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["LeftOf"] = Field(default="LeftOf", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class RightOf(SpatialRelationship):
    """
    The subject is laterally right of ego relative to ego's road heading, not merely in the right half of the image.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'exclusive_group': {'tag': 'exclusive_group',
                                             'value': 'lateral'},
                         'relation_extraction': {'tag': 'relation_extraction',
                                                 'value': 'enabled'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    subject: str = Field(default=..., description="""Perceived road user described relative to ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["RightOf"] = Field(default="RightOf", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class Near(SpatialRelationship):
    """
    The subject is within the configured near-distance threshold from ego in road coordinates.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    subject: str = Field(default=..., description="""Perceived road user described relative to ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["Near"] = Field(default="Near", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class RoadRegionRelationship(Relationship):
    """
    An abstract relationship from a road user to a road region.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    subject: str = Field(default=..., description="""Road user located in the road region.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Road region that contains the road user's ground reference point.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["RoadRegionRelationship"] = Field(default="RoadRegionRelationship", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class InLane(RoadRegionRelationship):
    """
    The subject's ground reference point lies in the lane.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'exclusive_group': {'tag': 'exclusive_group',
                                             'value': 'lane_membership'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships',
         'slot_usage': {'object': {'name': 'object', 'range': 'Lane'}}})

    subject: str = Field(default=..., description="""Road user located in the road region.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Road region that contains the road user's ground reference point.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["InLane"] = Field(default="InLane", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class InIntersection(RoadRegionRelationship):
    """
    The subject's ground reference point lies in the intersection.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'exclusive_group': {'tag': 'exclusive_group',
                                             'value': 'intersection_membership'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships',
         'slot_usage': {'object': {'name': 'object', 'range': 'Intersection'}}})

    subject: str = Field(default=..., description="""Road user located in the road region.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship', 'RoadRegionRelationship']} })
    object: str = Field(default=..., description="""Road region that contains the road user's ground reference point.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship', 'RoadRegionRelationship']} })
    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'RoadRegion', 'Relationship']} })
    type: Literal["InIntersection"] = Field(default="InIntersection", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['RoadUser', 'ObjectState', 'RoadRegion', 'Relationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'Relationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that support the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })


class Scene(ConfiguredBaseModel):
    """
    A road scene corresponding to one input frame.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema', 'tree_root': True})

    frame_id: str = Field(default=..., description="""Frame-local identifier assigned by the input stage.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    timestamp_ns: Optional[int] = Field(default=None, description="""Optional source timestamp in nanoseconds.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that contributed the frame represented by this scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EgoVehicle',
                       'PerceivedRoadUser',
                       'ObjectState',
                       'RoadRegion',
                       'Relationship',
                       'Scene']} })
    ego: EgoVehicle = Field(default=..., description="""The observing vehicle, which is not represented by an image bounding box.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    road_users: Optional[list[Union[PerceivedRoadUser,Vehicle,Cyclist,Pedestrian,Car,Truck,Bus,Motorcycle,SchoolBus]]] = Field(default=None, description="""Road users perceived in the frame, excluding ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    road_regions: Optional[list[Union[RoadRegion,Lane,Intersection]]] = Field(default=None, description="""Road regions perceived in the frame.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""States observed on perceived road users in this frame.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    relationships: Optional[list[Union[Relationship,SpatialRelationship,RoadRegionRelationship,InLane,InIntersection,InFrontOf,Behind,LeftOf,RightOf,Near]]] = Field(default=None, description="""Relationships between entities represented in the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Provenance.model_rebuild()
BoundingBox2D.model_rebuild()
RoadUserProvenance.model_rebuild()
RoadUser.model_rebuild()
EgoVehicle.model_rebuild()
PerceivedRoadUser.model_rebuild()
Vehicle.model_rebuild()
Car.model_rebuild()
Truck.model_rebuild()
Bus.model_rebuild()
SchoolBus.model_rebuild()
Motorcycle.model_rebuild()
Cyclist.model_rebuild()
Pedestrian.model_rebuild()
ObjectState.model_rebuild()
StopArmState.model_rebuild()
RoadRegion.model_rebuild()
Lane.model_rebuild()
Intersection.model_rebuild()
Relationship.model_rebuild()
SpatialRelationship.model_rebuild()
InFrontOf.model_rebuild()
Behind.model_rebuild()
LeftOf.model_rebuild()
RightOf.model_rebuild()
Near.model_rebuild()
RoadRegionRelationship.model_rebuild()
InLane.model_rebuild()
InIntersection.model_rebuild()
Scene.model_rebuild()
