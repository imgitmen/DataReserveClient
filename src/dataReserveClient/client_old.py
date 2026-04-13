from collections import defaultdict
from datetime import datetime
import json
import logging
from typing import Generic
import urllib
from annotated_types import T
import requests
from uuid import UUID
from urllib.parse import urlencode
from pydantic import validate_call
from pydantic import BaseModel

from .classes import DataItem
from .classes import SeriesStorage

class ValidationError(BaseModel):
    loc: str
    msg: str
    type: str   

class RequestResult(Generic[T]):
    status_code: int = 0
    errors: list[ValidationError] | None = None
    data: T | None = None
    
class HttpClient:
    __host: str
    __apikey: str | None
    __apiversion: str | None
    
    
    def __init__(self, host: str, apikey: str | None, apiversion: str | None):
        self.__logger = logging.getLogger()
        if host is None or host.__len__() == 0:
            raise ValueError("host")
        
        self.__host = host
        self.__apikey = apikey
        self.__apiversion = apiversion
        
        if self.__apiversion is None or self.__apiversion.strip() == "":
            self.__apiversion = "v1"
    
    def __create_url(self, endpoint: str, path: str | list[str] | None = None, query: dict | None = None):
        url = f"{self.__host}/api/{self.__apiversion}/{endpoint}/"
        splitted = []

        if path is not None:
            if type(path) == str:
                splitted = path.split("/")
                
            if type(path) == list:
                splitted = path
            
            for s in splitted:
                url += urllib.parse.quote(str(s)) + "/"
        
        if query is not None:
            qry = urlencode(query, doseq=True)    
            url += "?" + qry
        
        return url
    
    def __get(self, url, t = type) -> tuple[requests.Response, RequestResult]:
        result = RequestResult[t]()
        self.__logger.debug("calling url {Url}", Url = url)
        response = requests.get(url, headers={"X-API-Key":self.__apikey})
        result.status_code = response.status_code
        
        if response.ok:
            result.errors = None
        else:
            if result.status_code != 404 and result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None
        
        return [response, result]

    def __post_get(self, url, body: dict, t = type) -> RequestResult:
        result = RequestResult[t]
        self.__logger.debug("posting to url {Url}", Url = url)
        #print(body.__dict__)
        response = requests.post(url, data = json.dumps(body), headers={"X-API-Key":self.__apikey})
        result.status_code = response.status_code
        
        if response.ok:
            result.errors = None
        else:
            if result.status_code != 404 and result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None
        
        return [response, result]

    def __post(self, url, body: dict, t = type) -> RequestResult:
        result = RequestResult[t]
        self.__logger.debug("posting to url {Url}", Url = url)
        #print(body.__dict__)
        response = requests.post(url, data = json.dumps(body), headers={"X-API-Key":self.__apikey})
        result.status_code = response.status_code
        
        if response.ok:
            result.errors = None
            if t == type(UUID):
                result.data = UUID(response.headers["location"])
            else:
                result.data = response.headers["location"]
        else:
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None
        
        return result

    def __post_json(self, url, body: dict, t = type) -> RequestResult:
        result = RequestResult[t]
        self.__logger.debug("posting to url {Url}", Url = url)
        
        response = requests.post(url, json = body, headers={"X-API-Key":self.__apikey})
        result.status_code = response.status_code
        
        if response.ok:
            result.errors = None
            result.data = True
        else:
            self.__logger.debug(f"Error saving data, body was: {json.dumps(body, indent=2)}")
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None
        
        return result

    def __put(self, url, body: dict, t = type) -> RequestResult:
        result = RequestResult[t]
        self.__logger.debug("putting to url {Url}", Url = url)
        response = requests.put(url, data = json.dumps(body), headers={"X-API-Key":self.__apikey})
        result.status_code = response.status_code
        result.data = None
        
        if response.ok:
            result.errors = None
        else:
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
        
        return result
    
    def __delete(self, url, t = type) -> RequestResult:
        result = RequestResult[t]
        self.__logger.debug("calling delete on url {Url}", Url = url)
        response = requests.delete(url, headers={"X-API-Key":self.__apikey})
        result.status_code = response.status_code
        result.data = None

        if response.ok:
            result.errors = None
        else:
            if result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
        
        return result

    def __add_errors(self, result: RequestResult, errors):
            result_errors = []
            if errors is not None:
                for item in errors["detail"]:
                    validationError = ValidationError(loc=item["loc"][-1], msg=item["msg"], type=item["type"])
                    
                    result_errors.append(validationError)
                
            result.errors = result_errors


    #############################################################
    ################### SERIES STORAGE ##########################
    #############################################################

    @validate_call
    def get_series_storages(self, seriesId: UUID | list[UUID] | None = None, 
                    storageId: UUID | list[UUID] | None = None, 
                    databaseName: str | list[str] | None = None, 
                    tableName: str | list[str] | None = None
                ) -> RequestResult[list[SeriesStorage]]:
        
        kvp = {}
        
        if seriesId is not None:
            kvp["SeriesId"] = seriesId

        if storageId is not None:
            kvp["StorageId"] = storageId
            
        if databaseName is not None:
            kvp["DatabaseName"] = databaseName
            
        if tableName is not None:
            kvp["TableName"] = tableName
        
        url = self.__create_url(endpoint="series_storage", query=kvp)
        
        result = self.__get(url, type(list[SeriesStorage]))
        
        if result[0].ok:
            result[1].data = []
            for d in result[0].json():
                result[1].data.append(SeriesStorage(**d))
        
        return result[1]
        
    @validate_call
    def get_series_storage(self, seriesId: UUID) -> RequestResult[SeriesStorage]:
        url = self.__create_url(endpoint="series_storage") + str(seriesId)
        self.__logger.debug("calling url {Url}", Url = url)
        
        result = self.__get(url, type(SeriesStorage))
        
        if result[0].ok:
            result[1].data = SeriesStorage(**result[0].json())
        
        return result[1]
    
    @validate_call
    def create_update_series_storage(self, seriesId: UUID | str, storageId: UUID | str, databaseName: str, tableName: str) -> RequestResult[UUID]:
        url = self.__create_url(endpoint="series_storage")
        result = self.__post(url, {"SeriesId" : str(seriesId), "StorageId": str(storageId), "DatabaseName": databaseName, "TableName": tableName})
        
        return result



    #############################################################
    ######################### DATA ##############################
    #############################################################

    @validate_call
    def get_data(self, seriesId: UUID | list[UUID], 
                    fromTime: datetime | None = None, 
                    toTime: datetime | None = None
                ) -> RequestResult[list[DataItem]]:

        url = self.__create_url(endpoint="data/search")
        
        if not type(seriesId) is list:
            seriesId = [str(seriesId)]
        else:
            seriesId = [str(x) for x in seriesId]
        
        body = { "SeriesId" : seriesId, "FromTime" : fromTime, "ToTime" : toTime }
                    
        result = self.__post_get(url, body, type(list[DataItem]))
        
        if result[0].ok:
            result[1].data = []
            for d in result[0].json():
                result[1].data.append(DataItem(**d))
        
        return result[1]
        
    @validate_call
    def get_data_as_dict(self, seriesId: UUID | list[UUID], 
                    fromTime: datetime | None = None, 
                    toTime: datetime | None = None
                ) -> RequestResult[list[dict]]:

        url = self.__create_url(endpoint="data/search")
        
        if not type(seriesId) is list:
            seriesId = [str(seriesId)]
        else:
            seriesId = [str(x) for x in seriesId]
        
        body = { "SeriesId" : seriesId, "FromTime" : fromTime, "ToTime" : toTime }
                    
        result = self.__post_get(url, body, type(list[DataItem]))
        
        if result[0].ok:
            result[1].data = result[0].json()
        
        return result[1]
        
    @validate_call
    def save_data(self, data: list[DataItem]) -> RequestResult[bool]:
        url = self.__create_url(endpoint="data")
        data_dict = self.__translate_dataItem_list(data)
        result = self.__post_json(url, data_dict, type(bool))
        
        return result

    def __translate_dataItem_list(self, data: list[DataItem]):
        grouped = defaultdict(list)

        for item in data:
            grouped[str(item.SeriesId)].append({
                "Timestamp": item.Timestamp.isoformat(),
                "Value": item.Value
            })

        result = [
            {
                "SeriesId": series_id,
                "Data": data_list
            }
            for series_id, data_list in grouped.items()
        ]

        return result