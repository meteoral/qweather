"""
QWeather for Home Assistant
"""

import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.components.weather import (
    WeatherEntity, ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME, PLATFORM_SCHEMA)
from homeassistant.const import (ATTR_ATTRIBUTION, TEMP_CELSIUS, CONF_NAME)
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)
ATTR_CONDITION_CN = "condition_cn"
ATTR_UPDATE_TIME = "update_time"
ATTR_AQI = "aqi"
ATTR_HOURLY_FORECAST = "hourly_forecast"
ATTR_SUGGESTION = "suggestion"
ATTR_CUSTOM_UI_MORE_INFO = "custom_ui_more_info"
TIME_BETWEEN_UPDATES = timedelta(seconds=600)
DEFAULT_TIME = dt_util.now()
CONF_LOCATION = "location"
CONF_APPKEY = "appkey"

CONDITION_CLASSES = {
    'sunny': ["晴"],
    'cloudy': ["多云"],
    'partlycloudy': ["少云", "晴间多云", "阴"],
    'windy': ["有风", "微风", "和风", "清风"],
    'windy-variant': ["强风", "疾风", "大风", "烈风"],
    'hurricane': ["飓风", "龙卷风", "热带风暴", "狂暴风", "风暴"],
    'rainy': ["毛毛雨", "小雨", "中雨", "大雨", "阵雨", "极端降雨"],
    'pouring': ["暴雨", "大暴雨", "特大暴雨", "强阵雨"],
    'lightning-rainy': ["雷阵雨", "强雷阵雨"],
    'fog': ["雾", "薄雾"],
    'hail': ["雷阵雨伴有冰雹"],
    'snowy': ["小雪", "中雪", "大雪", "暴雪", "阵雪"],
    'snowy-rainy': ["雨夹雪", "雨雪天气", "阵雨夹雪"],
}

ATTR_UPDATE_TIME = "更新时间"
ATTRIBUTION = "来自和风天气的天气数据"


async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.info("setup entry weather. QWeather...")
    config = config_entry.data
    name = config.get(CONF_NAME)
    location = config.get(CONF_LOCATION)
    appkey = config.get(CONF_APPKEY)

    data = WeatherData(hass, location, appkey)

    await data.async_update(dt_util.now())
    async_track_time_interval(hass, data.async_update, TIME_BETWEEN_UPDATES)

    async_add_entities([QWeather(data, name, location)], True)


class QWeather(WeatherEntity):
    """Representation of a weather condition."""

    _attr_native_temperature_unit = TEMP_CELSIUS

    def __init__(self, data, name, location):
        """Initialize the  weather."""
        self._name = None
        self._object_id = name
        self._attr_unique_id = name
        self._condition = None
        self._temperature = None
        self._humidity = None
        self._pressure = None
        self._wind_speed = None
        self._wind_bearing = None
        self._forecast = None
        self._data = data
        self._updatetime = None
        self._aqi = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._object_id

    @property
    def registry_name(self):
        """返回实体的friendly_name属性."""
        return '{} {}'.format('和风天气', self._name)

    @property
    def should_poll(self):
        """attention No polling needed for a demo weather condition."""
        return True

    @property
    def temperature(self):
        """Return the temperature."""
        return self._temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._attr_native_temperature_unit

    @property
    def humidity(self):
        """Return the humidity."""
        return self._humidity

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._wind_speed

    @property
    def wind_bearing(self):
        """Return the wind speed."""
        return self._wind_bearing

    @property
    def pressure(self):
        """Return the pressure."""
        return self._pressure

    @property
    def condition(self):
        """Return the weather condition."""
        try:
            # print(self._condition)
            if self._condition:
                return [k for k, v in CONDITION_CLASSES.items() if self._condition in v][0]
        except Exception as ex:
            pass
        return 'unknown'

    @property
    def attribution(self):
        """Return the attribution."""
        return 'Powered by Home Assistant'

    @property
    def forecast(self):
        """Return the forecast."""
        if self._daily_forecast is None:
            return None
        reftime = datetime.now()

        forecast_data = []
        _LOGGER.debug('daily_forecast: %s', self._daily_forecast)
        for entry in self._daily_forecast:
            data_dict = {
                ATTR_FORECAST_CONDITION: entry[0],
                ATTR_FORECAST_TEMP: entry[1],
                ATTR_FORECAST_TEMP_LOW: entry[2],
                ATTR_FORECAST_TIME: entry[3],
                ATTR_FORECAST_PRECIPITATION: entry[4],
                ATTR_FORECAST_PROBABLE_PRECIPITATION: entry[5],
                "condition_cn": entry[6]
            }
            reftime = reftime + timedelta(days=1)
            forecast_data.append(data_dict)
        # _LOGGER.debug('forecast_data: %s', forecast_data)
        return forecast_data

    @property
    def hourly_forecast(self):
        """Return the forecast."""
        if self._hourly_forecast is None:
            return None
        forecast_data = []
        _LOGGER.debug('hourly_forecast: %s', self._hourly_forecast)
        for entry in self._hourly_forecast:
            data_dict = {
                ATTR_FORECAST_CONDITION: entry[0],
                ATTR_FORECAST_TEMP: entry[1],
                ATTR_FORECAST_TIME: entry[2],
                ATTR_FORECAST_PROBABLE_PRECIPITATION: entry[3],
                "condition_cn": entry[4]
            }
            forecast_data.append(data_dict)
        # _LOGGER.debug('hourly_forecast_data: %s', forecast_data)
        return forecast_data


    @property
    def state_attributes(self):
        attributes = super().state_attributes
        """设置其它一些属性值."""
        if self._condition is not None:
            attributes.update({
                "location": self._name,
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_UPDATE_TIME: self._updatetime,
                ATTR_CONDITION_CN: self._condition,
                ATTR_AQI: self._aqi,
                ATTR_HOURLY_FORECAST: self.hourly_forecast,
                ATTR_SUGGESTION: self._suggestion,
                ATTR_CUSTOM_UI_MORE_INFO: "qweather-more-info"
            })
        return attributes

    @property
    def device_state_attributes(self):
        """设置其它一些属性值."""
        if self._condition is not None:
            return {
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_UPDATE_TIME: self._updatetime
            }

    @property
    def forecast(self):
        """Return the forecast."""

        reftime = datetime.now()

        forecast_data = []
        for entry in self._forecast:
            data_dict = {
                ATTR_FORECAST_TIME: reftime.isoformat(),
                ATTR_FORECAST_CONDITION: entry[0],
                ATTR_FORECAST_TEMP: entry[1],
                ATTR_FORECAST_TEMP_LOW: entry[2]
            }
            reftime = reftime + timedelta(days=1)
            forecast_data.append(data_dict)

        return forecast_data

    @asyncio.coroutine
    def async_update(self, now=DEFAULT_TIME):
        """update函数变成了async_update."""
        self._updatetime = self._data.updatetime
        self._name = self._data.name
        self._condition = self._data.condition
        self._temperature = self._data.temperature
        _attr_native_temperature_unit = self._data.temperature_unit
        self._humidity = self._data.humidity
        self._pressure = self._data.pressure
        self._wind_speed = self._data.wind_speed
        self._wind_bearing = self._data.wind_bearing
        self._forecast = self._data.forecast
        self._aqi = self._data.aqi
        _LOGGER.info("success to update informations")


class WeatherData(object):
    """天气相关的数据，存储在这个类中."""

    def __init__(self, hass, location, key):
        """初始化函数."""
        self._hass = hass

        self._forecast_url_ = "https://devapi.qweather.com/v7/weather/7d?location=" + location + "&key=" + key
        self._weather_now_url = "https://devapi.qweather.com/v7/weather/now?location=" + location + "&key=" + key
        self.suggestion_url = "https://devapi.qweather.com/v7/indices/1d?location=" + location + "&key=" + key + "&type=0"
        self.hour_url = "https://devapi.qweather.com/v7/weather/24h?location=" + location + "&key=" + key
        self._params = {"location": location,
                        "key": key}

        self._name = None
        self._condition = None
        self._temperature = None
        self._temperature_unit = None
        self._humidity = None
        self._pressure = None
        self._wind_speed = None
        self._wind_bearing = None
        self._forecast = None
        self._updatetime = None

    @property
    def name(self):
        """地点."""
        return self._name

    @property
    def condition(self):
        """天气情况."""
        return self._condition

    @property
    def temperature(self):
        """温度."""
        return self._temperature

    @property
    def temperature_unit(self):
        """温度单位."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """湿度."""
        return self._humidity

    @property
    def pressure(self):
        """气压."""
        return self._pressure

    @property
    def wind_speed(self):
        """风速."""
        return self._wind_speed

    @property
    def wind_bearing(self):
        """风向."""
        return self._wind_bearing

    @property
    def forecast(self):
        """预报."""
        return self._forecast

    @property
    def updatetime(self):
        """更新时间."""
        return self._updatetime

    @asyncio.coroutine
    async def async_update(self, now):
        """从远程更新信息."""
        _LOGGER.info("Update from QWeather's OpenAPI...")

        # 通过HTTP访问，获取需要的信息
        # 此处使用了基于aiohttp库的async_get_clientsession
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            connector = aiohttp.TCPConnector(limit=10)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(self._weather_now_url) as response:
                    json_data = await response.json()
                    weather = json_data["now"]
                async with session.get(self._forecast_url_) as response:
                    json_data = await response.json()
                    forecast = json_data

        except(asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while accessing: %s", self._weather_now_url)
            return

        self._temperature = float(weather["temp"])
        self._humidity = float(weather["humidity"])
        self._pressure = weather["pressure"]
        self._condition = weather["text"]
        self._wind_speed = weather["windSpeed"]
        self._wind_bearing = weather["windDir"]

        # self._windDir = weather["windDir"]
        # self._windScale = weather["windScale"]
        # self._windSpeed = weather["windSpeed"]
        self._updatetime = weather["obsTime"]

        datemsg = forecast["daily"]

        forec_cond = []
        for n in range(7):
            for i, j in CONDITION_CLASSES.items():
                if datemsg[n]["textDay"] in j:
                    forec_cond.append(i)

        self._forecast = [
            [forec_cond[0], int(datemsg[0]["tempMax"]), int(datemsg[0]["tempMin"])],
            [forec_cond[1], int(datemsg[1]["tempMax"]), int(datemsg[1]["tempMin"])],
            [forec_cond[2], int(datemsg[2]["tempMax"]), int(datemsg[2]["tempMin"])],
            [forec_cond[3], int(datemsg[3]["tempMax"]), int(datemsg[3]["tempMin"])],
            [forec_cond[4], int(datemsg[4]["tempMax"]), int(datemsg[4]["tempMin"])],
            [forec_cond[5], int(datemsg[5]["tempMax"]), int(datemsg[5]["tempMin"])],
            [forec_cond[6], int(datemsg[6]["tempMax"]), int(datemsg[6]["tempMin"])]
        ]
        _LOGGER.info("success to load local informations")
