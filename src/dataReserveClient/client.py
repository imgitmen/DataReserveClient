from collections import defaultdict
from datetime import datetime
import json
import logging
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar, Union
import urllib
import requests
from uuid import UUID

from pydantic import BaseModel, validate_call

from .classes import DataItem
from .classes import SeriesStorage

T = TypeVar("T")


class ValidationError(BaseModel):
    loc: str
    msg: str
    type: str


class RequestResult(Generic[T]):
    status_code: int = 0
    errors: Optional[List[ValidationError]] = None
    data: Optional[T] = None


class HttpClient:
    __host: str
    __apikey: Optional[str]
    __apiversion: Optional[str]

    def __init__(self, host: str, apikey: Optional[str], apiversion: Optional[str]):
        self.__logger = logging.getLogger()

        if host is None or len(host) == 0:
            raise ValueError("host")

        self.__host = host
        self.__apikey = apikey
        self.__apiversion = apiversion

        if self.__apiversion is None or self.__apiversion.strip() == "":
            self.__apiversion = "v1"

    def __create_url(
        self,
        endpoint: str,
        path: Optional[Union[str, List[str]]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = f"{self.__host}/api/{self.__apiversion}/{endpoint}/"
        splitted: List[str] = []

        if path is not None:
            if isinstance(path, str):
                splitted = path.split("/")
            elif isinstance(path, list):
                splitted = path

            for s in splitted:
                url += urllib.parse.quote(str(s)) + "/"

        if query is not None:
            # requests gestisce bene i parametri multipli, ma qui mantengo la tua logica
            from urllib.parse import urlencode

            qry = urlencode(query, doseq=True)
            url += "?" + qry

        return url

    def __get(self, url: str, t: Any = None) -> Tuple[requests.Response, RequestResult[Any]]:
        result: RequestResult[Any] = RequestResult()
        self.__logger.debug("calling url %s", url)

        response = requests.get(url, headers={"X-API-Key": self.__apikey})
        result.status_code = response.status_code

        if response.ok:
            result.errors = None
        else:
            if response.status_code not in (404, 500):
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None

        return (response, result)

    def __post_get(
        self, url: str, body: Dict[str, Any], t: Any = None
    ) -> Tuple[requests.Response, RequestResult[Any]]:
        result: RequestResult[Any] = RequestResult()
        self.__logger.debug("posting to url %s", url)

        response = requests.post(
            url,
            data=json.dumps(body),
            headers={"X-API-Key": self.__apikey, "Content-Type": "application/json"},
        )
        result.status_code = response.status_code

        if response.ok:
            result.errors = None
        else:
            if response.status_code not in (404, 500):
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None

        return (response, result)

    def __post(self, url: str, body: Dict[str, Any], t: Any = None) -> RequestResult[Any]:
        result: RequestResult[Any] = RequestResult()
        self.__logger.debug("posting to url %s", url)

        response = requests.post(
            url,
            data=json.dumps(body),
            headers={"X-API-Key": self.__apikey, "Content-Type": "application/json"},
        )
        result.status_code = response.status_code

        if response.ok:
            result.errors = None
            location = response.headers.get("location")

            if t == UUID and location is not None:
                result.data = UUID(location)
            else:
                result.data = location
        else:
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None

        return result

    def __post_json(self, url: str, body: Dict[str, Any], t: Any = None) -> RequestResult[bool]:
        result: RequestResult[bool] = RequestResult()
        self.__logger.debug("posting to url %s", url)

        response = requests.post(url, json=body, headers={"X-API-Key": self.__apikey})
        result.status_code = response.status_code

        if response.ok:
            result.errors = None
            result.data = True
        else:
            self.__logger.debug("Error saving data, body was: %s", json.dumps(body, indent=2))
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None

        return result

    def __put(self, url: str, body: Dict[str, Any], t: Any = None) -> RequestResult[Any]:
        result: RequestResult[Any] = RequestResult()
        self.__logger.debug("putting to url %s", url)

        response = requests.put(
            url,
            data=json.dumps(body),
            headers={"X-API-Key": self.__apikey, "Content-Type": "application/json"},
        )
        result.status_code = response.status_code
        result.data = None

        if response.ok:
            result.errors = None
        else:
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)

        return result

    def __delete(self, url: str, t: Any = None) -> RequestResult[Any]:
        result: RequestResult[Any] = RequestResult()
        self.__logger.debug("calling delete on url %s", url)

        response = requests.delete(url, headers={"X-API-Key": self.__apikey})
        result.status_code = response.status_code
        result.data = None

        if response.ok:
            result.errors = None
        else:
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)

        return result

    def __add_errors(self, result: RequestResult[Any], errors: Dict[str, Any]) -> None:
        result_errors: List[ValidationError] = []

        if errors is not None and "detail" in errors:
            for item in errors["detail"]:
                validation_error = ValidationError(
                    loc=item["loc"][-1],
                    msg=item["msg"],
                    type=item["type"],
                )
                result_errors.append(validation_error)

        result.errors = result_errors

    #############################################################
    ################### SERIES STORAGE ##########################
    #############################################################

    @validate_call
    def get_series_storages(
        self,
        seriesId: Optional[Union[UUID, List[UUID]]] = None,
        storageId: Optional[Union[UUID, List[UUID]]] = None,
        databaseName: Optional[Union[str, List[str]]] = None,
        tableName: Optional[Union[str, List[str]]] = None,
    ) -> RequestResult[List[SeriesStorage]]:
        kvp: Dict[str, Any] = {}

        if seriesId is not None:
            kvp["SeriesId"] = seriesId

        if storageId is not None:
            kvp["StorageId"] = storageId

        if databaseName is not None:
            kvp["DatabaseName"] = databaseName

        if tableName is not None:
            kvp["TableName"] = tableName

        url = self.__create_url(endpoint="series_storage", query=kvp)

        response, result = self.__get(url, List[SeriesStorage])

        if response.ok:
            result.data = []
            for d in response.json():
                result.data.append(SeriesStorage(**d))

        return result

    @validate_call
    def get_series_storage(self, seriesId: UUID) -> RequestResult[SeriesStorage]:
        url = self.__create_url(endpoint="series_storage") + str(seriesId)
        self.__logger.debug("calling url %s", url)

        response, result = self.__get(url, SeriesStorage)

        if response.ok:
            result.data = SeriesStorage(**response.json())

        return result

    @validate_call
    def create_update_series_storage(
        self,
        seriesId: Union[UUID, str],
        storageId: Union[UUID, str],
        databaseName: str,
        tableName: str,
    ) -> RequestResult[Any]:
        url = self.__create_url(endpoint="series_storage")
        result = self.__post(
            url,
            {
                "SeriesId": str(seriesId),
                "StorageId": str(storageId),
                "DatabaseName": databaseName,
                "TableName": tableName,
            },
        )

        return result

    #############################################################
    ######################### DATA ##############################
    #############################################################

    @validate_call
    def get_data(
        self,
        seriesId: Union[UUID, List[UUID]],
        fromTime: Optional[datetime] = None,
        toTime: Optional[datetime] = None,
    ) -> RequestResult[List[DataItem]]:
        url = self.__create_url(endpoint="data/search")

        if not isinstance(seriesId, list):
            series_ids = [str(seriesId)]
        else:
            series_ids = [str(x) for x in seriesId]

        body = {
            "SeriesId": series_ids,
            "FromTime": fromTime.isoformat() if fromTime is not None else None,
            "ToTime": toTime.isoformat() if toTime is not None else None,
        }

        response, result = self.__post_get(url, body, List[DataItem])

        if response.ok:
            result.data = []
            for d in response.json():
                result.data.append(DataItem(**d))

        return result

    @validate_call
    def get_data_as_dict(
        self,
        seriesId: Union[UUID, List[UUID]],
        fromTime: Optional[datetime] = None,
        toTime: Optional[datetime] = None,
    ) -> RequestResult[List[Dict[str, Any]]]:
        url = self.__create_url(endpoint="data/search")

        if not isinstance(seriesId, list):
            series_ids = [str(seriesId)]
        else:
            series_ids = [str(x) for x in seriesId]

        body = {
            "SeriesId": series_ids,
            "FromTime": fromTime.isoformat() if fromTime is not None else None,
            "ToTime": toTime.isoformat() if toTime is not None else None,
        }

        response, result = self.__post_get(url, body, List[Dict[str, Any]])

        if response.ok:
            result.data = response.json()

        return result

    @validate_call
    def save_data(self, data: List[DataItem]) -> RequestResult[bool]:
        url = self.__create_url(endpoint="data")
        data_dict = self.__translate_dataItem_list(data)
        result = self.__post_json(url, data_dict, bool)

        return result

    def __translate_dataItem_list(self, data: List[DataItem]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for item in data:
            grouped[str(item.SeriesId)].append(
                {
                    "Timestamp": item.Timestamp.isoformat(),
                    "Value": item.Value,
                }
            )

        result = [
            {
                "SeriesId": series_id,
                "Data": data_list,
            }
            for series_id, data_list in grouped.items()
        ]

        return result