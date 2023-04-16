import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, TypeVar, Union

import pytz
import requests
from splight_lib.component import AbstractComponent
from splight_lib.execution import Task
from splight_lib.logging import getLogger
from splight_models import Number, String

from .client import SolarEdgeAPIClient

logger = getLogger()

# TO-DO
# 1. Apply checkpoint to all endpoints.
# 2. Move inverter code to SolarEdgeAPIClient.get_inverter_data(..)

SiteReader = TypeVar("SiteReader")
InverterReader = TypeVar("InverterReader")
Asset = TypeVar("Asset")
Attribute = TypeVar("Attribute")


class Main(AbstractComponent):
    _mappings = {
        "SiteReader": [],
        "InverterReader": [],
    }

    # _mappings = {
    #     "SiteReader": [SiteReader(asset=Asset(id='301742e1-9d5f-449a-947b-688850a129f7', name='SolarEdgeTest', description='desc', external_id=None, latitude=None, longitude=None, tags=[], attributes=[Attribute(id='f3d6ffc7-9f81-43a8-b8cf-04b90ff0a4a8', name='fm_inverter_totalEnergy'), Attribute(id='b3b42427-18e9-4c58-9cf7-202b613d5b7f', name='fm_inverter-dcVoltage'), Attribute(
    #         id='a9715cb3-600f-4696-b8a9-3847085f5eaa', name='inverter-totalActivePower'), Attribute(id='0cd358d1-9a73-4d8b-bc03-3c88e4b83d36', name='fm_inverter_temperature')], verified=False), attribute=Attribute(id='a9715cb3-600f-4696-b8a9-3847085f5eaa', name='inverter-totalActivePower'), resource='power', site_id='2757509', id='467b165c-cc3a-4264-802c-6b09dd77456e', name='power', description='descrp'),
    #         SiteReader(asset=Asset(id='301742e1-9d5f-449a-947b-688850a129f7', name='SolarEdgeTest', description='desc', external_id=None, latitude=None, longitude=None, tags=[], attributes=[Attribute(id='f3d6ffc7-9f81-43a8-b8cf-04b90ff0a4a8', name='fm_inverter_totalEnergy'), Attribute(id='b3b42427-18e9-4c58-9cf7-202b613d5b7f', name='energy'), Attribute(
    #             id='a9715cb3-600f-4696-b8a9-3847085f5eaa', name='inverter-totalActivePower'), Attribute(id='0cd358d1-9a73-4d8b-bc03-3c88e4b83d36', name='fm_inverter_temperature')], verified=False), attribute=Attribute(id='a9715cb3-600f-4696-b8a9-3847085f5eaa', name='inverter-totalActivePower'), resource='energy', site_id='2757509', id='467b165c-cc3a-4264-802c-6b09dd77456e', name='energy', description='descrp')],
    #     "InverterReader": [InverterReader(asset=Asset(id='301742e1-9d5f-449a-947b-688850a129f7', name='SolarEdgeTest', description='desc', external_id=None, latitude=None, longitude=None, tags=[], attributes=[Attribute(id='f3d6ffc7-9f81-43a8-b8cf-04b90ff0a4a8', name='fm_inverter_totalEnergy'), Attribute(id='b3b42427-18e9-4c58-9cf7-202b613d5b7f', name='fm_inverter-dcVoltage'), Attribute(
    #         id='a9715cb3-600f-4696-b8a9-3847085f5eaa', name='inverter-totalActivePower'), Attribute(id='0cd358d1-9a73-4d8b-bc03-3c88e4b83d36', name='fm_inverter_temperature')], verified=False), attribute=Attribute(id='a9715cb3-600f-4696-b8a9-3847085f5eaa', name='inverter-totalActivePower'), resource='L2Data.acFrequency', site_id='2757509', serial_number='7E04DFAD-0E', id='467b165c-cc3a-4264-802c-6b09dd77456e', name='L2Data.acFrequency', description='descrp')],
    # }

    # max backward days for inverter: 7
    # max backward days for other endpoints : 30
    _DEFAULT_CHECKPOINT_BACKWARDS_DAYS = 6
    _TIMESTAMP_FORMAT = "%Y-%m-%d %H"
    energy_checkpoint = (
        pytz.timezone("utc")
        .localize(
            datetime.utcnow()
            - timedelta(days=_DEFAULT_CHECKPOINT_BACKWARDS_DAYS)
        )
        .strftime("%Y-%m-%d %H:%M:%S")
    )
    power_checkpoint = energy_checkpoint

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.client = SolarEdgeAPIClient(api_key=self.input.api_key)
        self._fetch_existing_mappings()

    def _fetch_existing_mappings(self):
        self._mappings["SiteReader"]: List[
            SiteReader
        ] = self.database_client.get(self.custom_types.SiteReader)
        self._mappings["InverterReader"]: List[
            SiteReader
        ] = self.database_client.get(self.custom_types.InverterReader)

        for mapping_type, mappings in self._mappings.items():
            for mapping in mappings:
                pass
                # self._checkpoints[mapping]= pytz.timezone("utc").localize(datetime.utcnow() - timedelta(days=_DEFAULT_CHECKPOINT_BACKWARDS_DAYS)).strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"Readers found: {self._mappings}")

    def start(self) -> None:
        self.execution_client.start(
            Task(
                handler=self.task,
                args=(),
                period=60 * 0.10,
            )
        )

    def task(self) -> None:
        instances = []
        logger.info(f"Current mappings: self._mappings")
        for site_reader in self._mappings["SiteReader"]:
            if site_reader.resource == "power":
                end_time = datetime.now()
                start_time = datetime.now() - timedelta(
                    days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS
                )
                resource = site_reader.resource

                data = self.client.get_power(
                    site_id=site_reader.site_id,
                    start_time=start_time,
                    end_time=end_time,
                )

                if data:
                    data_to_save = [
                        Number(
                            asset=site_reader.asset.id,
                            attribute=site_reader.attribute.id,
                            value=value["value"],
                            timestamp=value["date"],
                        )
                        for value in data[site_reader.resource]["values"]
                        if value["value"] is not None
                    ]
                    self.datalake_client.save(instances=data_to_save)
                    logger.info(
                        f"Power data added length: {len(data_to_save)}"
                    )
                else:
                    logger.info(
                        f"No power data added, length: {len(data_to_save)}"
                    )

            if site_reader.resource == "energy":
                end_date = datetime.now()
                start_date = datetime.now() - timedelta(
                    days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS
                )
                resource = site_reader.resource

                data = self.client.get_energy(
                    site_id=site_reader.site_id,
                    start_date=start_date,
                    end_date=end_date,
                )
                data_to_save = []
                if data:
                    data_to_save = [
                        Number(
                            asset=site_reader.asset.id,
                            attribute=site_reader.attribute.id,
                            value=value["value"],
                            timestamp=value["date"],
                        )
                        for value in data[site_reader.resource]["values"]
                        if (
                            value["value"] is not None
                            and value["date"] > self.energy_checkpoint
                        )
                    ]
                    self.datalake_client.save(instances=data_to_save)
                    if data_to_save:
                        self.energy_checkpoint = max(
                            self.energy_checkpoint,
                            data_to_save[-1].timestamp.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        )

                    logger.info(
                        f"Energy data added length: {len(data_to_save)}"
                    )
                else:
                    logger.info(
                        f"No Energy data added, length: {len(data_to_save)}"
                    )

        inverter_readers_grouped_by_id = {}
        for inverter in self._mappings["InverterReader"]:
            if inverter.serial_number in inverter_readers_grouped_by_id:
                inverter_readers_grouped_by_id[inverter.serial_number].append(
                    inverter
                )
            else:
                inverter_readers_grouped_by_id[inverter.serial_number] = [
                    inverter
                ]
        logger.info(inverter_readers_grouped_by_id)
        for inverter_id in inverter_readers_grouped_by_id:
            endTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            startTime = (
                datetime.now()
                - timedelta(days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS)
            ).strftime("%Y-%m-%d %H:%M:%S")
            inverter_id = inverter.serial_number
            site_id = inverter.site_id
            # try:
            url = f"https://monitoringapi.solaredge.com/equipment/{site_id}/{inverter_id}/data?startTime={startTime}&endTime={endTime}"
            params = {
                "api_key": self.input.api_key,
            }
            response = requests.get(url, params=params)
            data = json.loads(response.text)
            for inverter_reader in inverter_readers_grouped_by_id[inverter_id]:
                logger.info("inverter_reader")
                data_to_save = []
                if "." in inverter_reader.resource:
                    # per phase data
                    phase, data_key = inverter_reader.resource.split(".")
                    logger.info(f"phase: {phase}, data_key: {data_key}")
                    data_to_save = [
                        Number(
                            asset=inverter_reader.asset.id,
                            attribute=inverter_reader.attribute.id,
                            value=value[phase][data_key],
                            timestamp=value["date"],
                        )
                        for value in data["data"]["telemetries"]
                        if phase in value
                        and value[phase].get(data_key) is not None
                    ]
                    logger.info(
                        f"resource:{inverter_reader.resource}------data length{len(data_to_save)}---------------------------"
                    )
                else:
                    # inverter data
                    data_to_save = [
                        Number(
                            asset=inverter_reader.asset.id,
                            attribute=inverter_reader.attribute.id,
                            value=value[inverter_reader.resource],
                            timestamp=value["date"],
                        )
                        for value in data["data"]["telemetries"]
                        if value.get(inverter_reader.resource) is not None
                    ]
                    self.datalake_client.save(instances=data_to_save)
                    logger.info(
                        f"resource:{inverter_reader.resource}------data length{len(data_to_save)}---------------------------"
                    )

    def handle_mapping_create(
        self, reader: Union[SiteReader, InverterReader], mapping_type
    ) -> None:
        try:
            self._mappings[mapping_type].append(reader)
            logger.info(f"mapping added {self.site_attribute_to_dict(reader)}")
            # self._checkpoints[reader] = pytz.timezone("utc").localize(datetime.utcnow(
            # ) - timedelta(days=_DEFAULT_CHECKPOINT_BACKWARDS_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.error(
                f"""
                    SiteReader was not added succesfully due to the
                    following error. Delete the object and try again.
                    Error: {str(e)}
                    """
            )

    def handle_site_reader_create(self, reader: SiteReader):
        return self.handle_mapping_create(
            self, reader, mapping_type="SiteReader"
        )

    def handle_inverter_reader_create(self, reader: SiteReader):
        return self.handle_mapping_create(
            self, reader, mapping_type="InverterReader"
        )

    def handle_site_reader_delete(
        self, site_attribute_to_delete: SiteReader
    ) -> None:
        if site_attribute_to_delete in self._mappings["SiteReader"]:
            self._mappings["SiteReader"].remove(site_attribute_to_delete)
            logger.info(
                f"Deleted mapping for object_address {site_attribute_to_delete}"
            )
        else:
            logger.info(
                f"No existing mapping for object_address {site_attribute_to_delete}"
            )

    def handle_inverter_reader_delete(
        self, site_attribute_to_delete: InverterReader
    ) -> None:
        if site_attribute_to_delete in self._mappings["SiteReader"]:
            self._mappings["InverterReader"].remove(site_attribute_to_delete)
            logger.info(
                f"Deleted mapping for object_address {site_attribute_to_delete}"
            )
        else:
            logger.info(
                f"No existing mapping for object_address {site_attribute_to_delete}"
            )

    def site_attribute_to_dict(self, new_site_attribute: SiteReader) -> Dict:
        _dict = {
            "id": new_site_attribute.id,
            "asset_id": new_site_attribute.asset.id,
            "asset_name": new_site_attribute.asset.name,
            "attribute_id": new_site_attribute.attribute.id,
            "attribute_name": new_site_attribute.attribute.name,
            "resource": new_site_attribute.resource,
        }
        return _dict

    def log_site_attributes(self) -> None:
        for attribute in self.site_attributes:
            logger.info(
                f"""
                SiteReader:
                    Asset:
                        id: {attribute["asset_id"]}
                        name: {attribute["asset_name"]}
                    Site ID: {attribute["resource"].site_id}
                    Data Type: {attribute["data_type"]}
                """
            )

    def log_instances(self, instances: List[Number]) -> None:
        for instance in instances:
            logger.info(
                f"""
                Instance:
                    timestamp: {instance.timestamp},
                    value: {instance.value},
                    asset: {instance.asset})
                """
            )
