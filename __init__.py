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


SiteReader = TypeVar("SiteReader")
InverterReader = TypeVar("InverterReader")
Asset = TypeVar("Asset")
Attribute = TypeVar("Attribute")


class Main(AbstractComponent):
    _mappings = {
        "SiteReader": [],
        "InverterReader": [],
    }
    _checkpoints = {}
    # max backward days for inverter: 7
    # max backward days for other endpoints : 30
    _DEFAULT_CHECKPOINT_BACKWARDS_DAYS = 6
    _TIMESTAMP_FORMAT = "%Y-%m-%d %H"

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
                self._checkpoints[mapping] = (
                    pytz.timezone("utc")
                    .localize(
                        datetime.utcnow()
                        - timedelta(
                            days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS
                        )
                    )
                    .strftime("%Y-%m-%d %H:%M:%S")
                )

    def start(self) -> None:
        self.execution_client.start(
            Task(
                handler=self.task,
                args=(),
                period=self.input.request_period,
            )
        )

    def task(self) -> None:
        logger.info(f"Current mappings: {self._mappings}")
        for site_reader in self._mappings["SiteReader"]:
            if site_reader.resource not in ["power", "energy"]:
                continue

            data_to_save = self.retrieve_site_data(site_reader=site_reader)
            if data_to_save:
                self.datalake_client.save(instances=data_to_save)
                self._checkpoints[site_reader] = max(
                    self._checkpoints[site_reader],
                    data_to_save[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                )

            logger.info(
                f"{site_reader.resource.capitalize()} data added length: {len(data_to_save)}"
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
        for inverter_id in inverter_readers_grouped_by_id:
            site_id = inverter_readers_grouped_by_id[inverter_id][0].site_id
            serial_number = inverter_readers_grouped_by_id[inverter_id][
                0
            ].serial_number
            data_to_save = self.retrieve_inverter_data(
                site_id=site_id, serial_number=serial_number
            )

            for inverter_reader in inverter_readers_grouped_by_id[inverter_id]:
                self.save_inverter_data(
                    inverter_reader=inverter_reader, data_to_save=data_to_save
                )

    def retrieve_site_data(self, site_reader):
        if site_reader.resource == "power":
            end_time = datetime.now()
            start_time = datetime.now() - timedelta(
                days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS
            )

            data = self.client.get_power(
                site_id=site_reader.site_id,
                start_time=start_time,
                end_time=end_time,
            )

        elif site_reader.resource == "energy":
            end_date = datetime.now()
            start_date = datetime.now() - timedelta(
                days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS
            )

            data = self.client.get_energy(
                site_id=site_reader.site_id,
                start_date=start_date,
                end_date=end_date,
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
                if (
                    value["value"] is not None
                    and value["date"] > self._checkpoints[site_reader]
                )
            ]
            return data_to_save
        else:
            return []

    def retrieve_inverter_data(self, site_id, serial_number):
        end_time = datetime.now()
        start_time = datetime.now() - timedelta(
            days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS
        )

        data_to_save = self.client.get_inverter_data(
            site_id=site_id,
            inverter_id=serial_number,
            start_time=start_time,
            end_time=end_time,
        )
        if data_to_save:
            return data_to_save
        else:
            return []

    def save_inverter_data(self, inverter_reader, data_to_save):
        if "." in inverter_reader.resource:
            # per phase data
            phase, data_key = inverter_reader.resource.split(".")
            data_to_save = [
                Number(
                    asset=inverter_reader.asset.id,
                    attribute=inverter_reader.attribute.id,
                    value=value[phase][data_key],
                    timestamp=value["date"],
                )
                for value in data_to_save["data"]["telemetries"]
                if (
                    phase in value
                    and value[phase].get(data_key) is not None
                    and value["date"] > self._checkpoints[inverter_reader]
                )
            ]
        else:
            # inverter data
            data_to_save = [
                Number(
                    asset=inverter_reader.asset.id,
                    attribute=inverter_reader.attribute.id,
                    value=value[inverter_reader.resource],
                    timestamp=value["date"],
                )
                for value in data_to_save["data"]["telemetries"]
                if (
                    value.get(inverter_reader.resource) is not None
                    and value["date"] > self._checkpoints[inverter_reader]
                )
            ]
        if data_to_save:
            self.datalake_client.save(instances=data_to_save)
            self._checkpoints[inverter_reader] = max(
                self._checkpoints[inverter_reader],
                data_to_save[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            )

        logger.info(
            f"{inverter_reader.resource} data added length: {len(data_to_save)}"
        )

    def handle_mapping_create(
        self, reader: Union[SiteReader, InverterReader], mapping_type
    ) -> None:
        self._mappings[mapping_type].append(reader)
        self._checkpoints[reader] = (
            pytz.timezone("utc")
            .localize(
                datetime.utcnow()
                - timedelta(days=self._DEFAULT_CHECKPOINT_BACKWARDS_DAYS)
            )
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        logger.info(
            f"mapping added {self.site_attribute_to_dict(reader)}, chekpoint: {self._checkpoints[reader]}"
        )

    def handle_site_reader_create(self, reader: SiteReader):
        return self.handle_mapping_create(reader, mapping_type="SiteReader")

    def handle_inverter_reader_create(self, reader: InverterReader):
        return self.handle_mapping_create(
            reader, mapping_type="InverterReader"
        )

    def handle_mapping_delete(
        self, reader: Union[SiteReader, InverterReader], mapping_type
    ) -> None:
        if reader in self._mappings[mapping_type]:
            self._mappings[mapping_type].remove(reader)
            self._checkpoints.remove(reader)
            logger.info(f"Deleted mapping for object_address {reader}")
        else:
            logger.info(f"No existing mapping for object_address {reader}")

    def handle_site_reader_delete(self, reader: SiteReader) -> None:
        self.handle_mapping_delete(reader=reader, mapping_type="SiteReader")

    def handle_inverter_reader_delete(self, reader: InverterReader) -> None:
        self.handle_mapping_delete(
            reader=reader, mapping_type="InverterReader"
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
