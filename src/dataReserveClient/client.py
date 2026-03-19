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

from .classes import DataItem

class ValidationError():
    loc: str
    msg: str
    type: str   

class RequestResult(Generic[T]):
    status_code: int
    errors: list[ValidationError] | None
    data: T | None
    
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
        url = self.__host + f"/api/{self.__apiversion}/{endpoint}/"
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
        result = RequestResult[t]
        self.__logger.debug("calling url {Url}", Url = url)
        response = requests.get(url, headers={"X-API-Key":self.__apikey})
        result.status_code = response.status_code
        
        if response.ok:
            result.errors = None
        else:
            if response.status_code != 404 and result.status_code != 500:
                response_json = response.json()
                self.__add_errors(result, response_json)
            result.data = None
        
        return [response, result]

    def __post(self, url, body: dict, t = type) -> RequestResult:
        result = RequestResult[t]
        self.__logger.debug("posting to url {Url}", Url = url)
        #print(body)
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
                    validationError = ValidationError()
                    validationError.loc = item["loc"][-1]
                    validationError.msg = item["msg"]
                    validationError.type = item["type"]
                    result_errors.append(validationError)
                
            result.errors = result_errors

    #############################################################
    ######################### DATA ##############################
    #############################################################

    @validate_call
    def get_data(self, seriesId: UUID | list[UUID], 
                    fromTime: datetime | None = None, 
                    toTime: datetime | None = None
                ) -> RequestResult[list[DataItem]]:

        kvp = {}
        
        if seriesId is not None:
            kvp["SeriesId"] = seriesId

        if fromTime is not None:
            kvp["FromTime"] = fromTime
            
        if toTime is not None:
            kvp["ToTime"] = toTime

        url = self.__create_url(endpoint="data", query=kvp)
        
        result = self.__get(url, type(list[DataItem]))
        
        if result[0].ok:
            result[1].data = []
            for d in result[0].json():
                result[1].data.append(d)
        
        return result[1]
        
    @validate_call
    def save_data(self, data: list[DataItem]) -> RequestResult[UUID]:
        url = self.__create_url(endpoint="data")
        data_dict = self.__translate_dataItem_list(data)
        result = self.__post(url, data_dict, type(str))
        
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