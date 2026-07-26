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
                    'contains only the road-user types, object state, and '
                    'ego-relative spatial relationships that the current pipeline '
                    'supports.',
     'id': 'https://w3id.org/sgg-vlm/schema',
     'imports': ['linkml:types', 'common', 'states', 'road_users', 'relationships'],
     'name': 'sgg_vlm',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'sggvlm': {'prefix_prefix': 'sggvlm',
                             'prefix_reference': 'https://w3id.org/sgg-vlm/'}},
     'source_file': 'schema/scene_graph.yaml'} )

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
    unknown = "unknown"
    """
    The stop arm was evaluated but its position could not be determined.
    """


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


class ObjectState(ConfiguredBaseModel):
    """
    An abstract provenance-carrying state observed on a perceived road user.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/sgg-vlm/schema/states'})

    type: Literal["ObjectState"] = Field(default="ObjectState", description="""Concrete LinkML class of this object state.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the state assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the state assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


class StopArmState(ObjectState):
    """
    An assertion about a school bus's mounted stop arm.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/states'})

    value: StopArmStateValue = Field(default=..., description="""Asserted stop-arm position.""", json_schema_extra = { "linkml_meta": {'domain_of': ['StopArmState']} })
    type: Literal["StopArmState"] = Field(default="StopArmState", description="""Concrete LinkML class of this object state.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the state assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the state assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


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

    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["RoadUser"] = Field(default="RoadUser", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class EgoVehicle(RoadUser):
    """
    The observing vehicle and reference frame for spatial relationships.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users',
         'slot_usage': {'id': {'equals_string': 'ego', 'name': 'id'}}})

    provenance: list[Provenance] = Field(default=..., description="""Source establishing ego for this scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: Literal["ego"] = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship'], 'equals_string': 'ego'} })
    type: Literal["EgoVehicle"] = Field(default="EgoVehicle", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class PerceivedRoadUser(RoadUser):
    """
    A non-ego road user localized in the input image.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["PerceivedRoadUser"] = Field(default="PerceivedRoadUser", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class Vehicle(PerceivedRoadUser):
    """
    An abstract perceived motor vehicle.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Vehicle"] = Field(default="Vehicle", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class Car(Vehicle):
    """
    A passenger car.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'car'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Car"] = Field(default="Car", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class Truck(Vehicle):
    """
    A truck.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'truck'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Truck"] = Field(default="Truck", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class Bus(Vehicle):
    """
    A passenger bus that is not necessarily a school bus.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'bus'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Bus"] = Field(default="Bus", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class SchoolBus(Bus):
    """
    A bus used to transport students.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'school bus'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["SchoolBus"] = Field(default="SchoolBus", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class Motorcycle(Vehicle):
    """
    A motorcycle.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'motorcycle'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Motorcycle"] = Field(default="Motorcycle", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class Cyclist(PerceivedRoadUser):
    """
    A person riding a bicycle.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'cyclist'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Cyclist"] = Field(default="Cyclist", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class Pedestrian(PerceivedRoadUser):
    """
    A person traveling on foot.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'object_detection_prompt': {'tag': 'object_detection_prompt',
                                                     'value': 'pedestrian'}},
         'from_schema': 'https://w3id.org/sgg-vlm/schema/road-users'})

    bbox: BoundingBox2D = Field(default=..., description="""Image-space bounding box in pixel XYXY coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    track_id: Optional[str] = Field(default=None, description="""Optional cross-frame identity for the same physical road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    states: Optional[list[Union[ObjectState,StopArmState]]] = Field(default=None, description="""Observed states applicable to this road user.""", json_schema_extra = { "linkml_meta": {'domain_of': ['PerceivedRoadUser']} })
    provenance: list[RoadUserProvenance] = Field(default=..., description="""Sources supporting the existence, classification, bounding box, or tracking decisions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    id: str = Field(default=..., description="""Identity used to reference this road user within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Pedestrian"] = Field(default="Pedestrian", description="""Concrete LinkML class of this road user.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })


class SpatialRelationship(ConfiguredBaseModel):
    """
    An abstract spatial relationship from a perceived road user to ego in road coordinates.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["SpatialRelationship"] = Field(default="SpatialRelationship", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose position is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


class InFrontOf(SpatialRelationship):
    """
    The subject is longitudinally ahead of ego in road coordinates.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["InFrontOf"] = Field(default="InFrontOf", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose position is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


class Behind(SpatialRelationship):
    """
    The subject is longitudinally behind ego in road coordinates.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Behind"] = Field(default="Behind", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose position is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


class LeftOf(SpatialRelationship):
    """
    The subject is laterally left of ego relative to ego's road heading.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["LeftOf"] = Field(default="LeftOf", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose position is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


class RightOf(SpatialRelationship):
    """
    The subject is laterally right of ego relative to ego's road heading.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["RightOf"] = Field(default="RightOf", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose position is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


class Near(SpatialRelationship):
    """
    The subject is within the configured near-distance threshold from ego in road coordinates.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema/relationships'})

    id: str = Field(default=..., description="""Identity of this relationship within the scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['RoadUser', 'SpatialRelationship']} })
    type: Literal["Near"] = Field(default="Near", description="""Concrete LinkML class of this relationship.""", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['ObjectState', 'RoadUser', 'SpatialRelationship']} })
    subject: str = Field(default=..., description="""Perceived road user whose position is being described.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    object: str = Field(default=..., description="""Ego vehicle used as the spatial reference.""", json_schema_extra = { "linkml_meta": {'domain_of': ['SpatialRelationship']} })
    confidence: Optional[float] = Field(default=None, description="""Final normalized confidence in the relationship assertion.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState', 'SpatialRelationship']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources supporting the relationship assertion.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })


class Scene(ConfiguredBaseModel):
    """
    A road scene corresponding to one input frame.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/sgg-vlm/schema', 'tree_root': True})

    frame_id: str = Field(default=..., description="""Frame-local identifier assigned by the input stage.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    timestamp_ns: Optional[int] = Field(default=None, description="""Optional source timestamp in nanoseconds.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    provenance: list[Provenance] = Field(default=..., description="""Sources that contributed the frame represented by this scene.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ObjectState',
                       'EgoVehicle',
                       'PerceivedRoadUser',
                       'SpatialRelationship',
                       'Scene']} })
    ego: EgoVehicle = Field(default=..., description="""The observing vehicle, which is not represented by an image bounding box.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    road_users: Optional[list[Union[PerceivedRoadUser,Vehicle,Cyclist,Pedestrian,Car,Truck,Bus,Motorcycle,SchoolBus]]] = Field(default=None, description="""Road users perceived in the frame, excluding ego.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })
    relationships: Optional[list[Union[SpatialRelationship,InFrontOf,Behind,LeftOf,RightOf,Near]]] = Field(default=None, description="""Ego-relative spatial relationships derived in road coordinates.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Scene']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Provenance.model_rebuild()
BoundingBox2D.model_rebuild()
ObjectState.model_rebuild()
StopArmState.model_rebuild()
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
SpatialRelationship.model_rebuild()
InFrontOf.model_rebuild()
Behind.model_rebuild()
LeftOf.model_rebuild()
RightOf.model_rebuild()
Near.model_rebuild()
Scene.model_rebuild()
