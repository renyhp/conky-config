import json
import os
from datetime import timedelta, datetime

import dateutil.parser
import requests
from dateutil import tz

API_active = True

DIRECTIONS = ('↓', '↙', '←', '↖', '↑', '↗', '→', '↘', '↓', '-')
DIRECTION_IMG = (
    'N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N', 'CLM')
BEAUFORT = ('Calma', 'Bava di vento', 'Brezza leggera', 'Brezza tesa', 'Vento moderato', 'Vento teso', 'Vento fresco',
            'Vento forte', 'Burrasca', 'Burrasca forte', 'Tempesta', 'Tempesta violenta', 'Uragano')
WEEKDAYS = {
    "Sun": "dom",
    "Mon": "lun",
    "Tue": "mar",
    "Wed": "mer",
    "Thu": "gio",
    "Fri": "ven",
    "Sat": "sab"
}

ICONS = {
    "freezing_rain": 0xf017,
    "ice_pellets": 0xf01b,
    "snow": 0xf076,
    "flurries": 0xf082,
    "tstorm": 0xf016,
    "rain": 0xf01c,
    "fog": 0xf021,
    "cloudy": 0xf041,
    "mostly_cloudy": 0xf013,
    "partly_cloudy": [0xf031, 0xf086],
    "mostly_clear": [0xf083, 0xf081],
    "clear": [0xf00d, 0xf02e]
}

IMGS = {
    "freezing_rain_heavy": 26,
    "freezing_rain": 26,
    "freezing_rain_light": 29,
    "freezing_drizzle": 29,
    "ice_pellets_heavy": 25,
    "ice_pellets": 25,
    "ice_pellets_light": 25,
    "snow_heavy": 22,
    "snow": 19,
    "snow_light": [20, 43],
    "flurries": [21, 43],
    "tstorm": 15,
    "rain_heavy": 18,
    "rain": 12,
    "rain_light": [13, 40],
    "drizzle": [14, 39],
    "fog_light": [5, 37],
    "fog": 11,
    "cloudy": 7,
    "mostly_cloudy": [6, 38],
    "partly_cloudy": [4, 36],
    "mostly_clear": [2, 34],
    "clear": [1, 33]
}


def api_limit_exceeded():
    return any(type(response) == dict and response.get('message', None) == "API rate limit exceeded"
               for response in (current, hourly, daily))


def read_file(filename):
    with open(f"{os.environ['HOME']}/.conky/climacell/{filename}.json", 'r') as json_file:
        return json.load(json_file)


warning = ""

if API_active:
    current, hourly, daily = (requests.request("GET", url, params={
        "unit_system": "si",
        "lat": YOUR-LATITUDE,
        "lon": YOUR-LONGITUDE,
        "apikey": YOUR-API-KEY,
        "fields": fields
    }).json() for url, fields in
                              (("https://api.climacell.co/v3/weather/realtime",
                                "weather_code,feels_like,wind_speed,wind_direction,wind_gust,cloud_base,sunset,sunrise,"
                                "temp,cloud_cover,visibility,baro_pressure,humidity"),
                               ("https://api.climacell.co/v3/weather/forecast/hourly",
                                "weather_code,feels_like,wind_speed,wind_direction,wind_gust,cloud_base,sunset,sunrise,"
                                "precipitation,precipitation_probability,temp,cloud_cover"),
                               ("https://api.climacell.co/v3/weather/forecast/daily",
                                "weather_code")
                               ))

if not API_active or api_limit_exceeded():
    current, hourly, daily = (read_file(filename) for filename in ('current', 'hourly', 'daily'))
    warning = "!"

if api_limit_exceeded():
    print("API rate limit exceeded")
    exit(0)
elif API_active:
    for weather, filename in ((current, 'current'), (hourly, 'hourly'), (daily, 'daily')):
        with open(f"{os.environ['HOME']}/.conky/climacell/{filename}.json", 'w') as jsonfile:
            jsonfile.write(json.dumps(weather, indent=4))


def get_timestamp(isodate):
    return dateutil.parser.isoparse(isodate).astimezone(tz.tzlocal())


def mps_to_beaufort(speed):
    return 1.13 * speed ** (2 / 3)


def format_day(time: datetime):
    time = time.strftime('%a %d/%m')
    for eng, ita in WEEKDAYS.items():
        time = time.replace(eng, ita)
    return time


def format_number(num, order_of_magnitude=0, pad=2, max_value=99):
    rounded = round(num / 10 ** order_of_magnitude, num < 10 ** order_of_magnitude)
    if rounded == 0:
        return '0'.rjust(pad, ' ')
    if rounded > max_value:
        rounded = max_value
    return str(rounded).lstrip('0').rstrip('0').rstrip('.').rjust(pad, ' ')


class ClimaCellWeather:
    __slots__ = ['timestamp', 'sunrise', 'sunset', 'code', 'feels_like', 'wind', 'wind_gust', 'gusts', 'wind_direction',
                 'cloud_base', 'temperature', 'cover', 'visibility', 'pressure', 'humidity', 'precipitation',
                 'probability']

    def __init__(self, weather: dict):
        self.timestamp = get_timestamp(weather['observation_time']['value'])
        self.sunrise = get_timestamp(weather['sunrise']['value'])
        self.sunset = get_timestamp(weather['sunset']['value'])
        self.code = weather['weather_code']['value']
        self.feels_like = weather['feels_like']['value']
        wind_mps = weather['wind_speed']['value']
        gust_mps = weather['wind_gust']['value'] or 0
        self.wind = mps_to_beaufort(wind_mps)
        self.wind_gust = mps_to_beaufort(gust_mps)
        self.gusts = gust_mps > 8.2 and wind_mps - gust_mps > 4.6  # https://en.wikipedia.org/wiki/Wind_gust
        self.wind_direction = round(direction / 22.5) if (
                (direction := weather['wind_direction']['value']) is not None) else -1
        self.cloud_base = weather['cloud_base']['value']

    def is_night(self):
        return not self.sunrise <= self.timestamp <= self.sunset


class CurrentWeather(ClimaCellWeather):
    def __init__(self, weather: dict):
        super().__init__(weather)
        self.temperature = weather['temp']['value']
        self.cover = weather['cloud_cover']['value']
        self.visibility = weather['visibility']['value']
        self.pressure = weather['baro_pressure']['value']
        self.humidity = weather['humidity']['value']

    def to_string(self, voffset):
        def get_beaufort_description(beaufort_wind):
            try:
                description = BEAUFORT[round(beaufort_wind)]
            except IndexError:
                description = BEAUFORT[-1]
            addline = ' ' not in description
            description = description.rsplit(' ', 1)
            if addline:
                description.append('')
            return description

        img = IMGS[self.code]
        if type(img) == list:
            img = img[self.is_night()]
        wind_img = DIRECTION_IMG[self.wind_direction]
        wind = round(self.wind, 1)
        wind_gusts = round(self.wind_gust, 1)
        wind_gusts = f">{wind_gusts}<" if self.gusts else f"({wind_gusts})"
        wind_description = get_beaufort_description(self.wind)

        def make_line(key, value, pre=""):
            if pre:
                pre = "${goto 118}" + pre
            return f"{pre}${{goto 235}}${{color1}}{key.upper()}: $color${{alignr}}{value}"

        weather_info = (
            make_line('Temperatura', f"{round(self.temperature, 1)}°"),
            make_line('Percepita', f"{round(self.feels_like, 1)}°"),
            make_line('Umidità', f"{round(self.humidity, 1)}%"),
            make_line('Pressione', f"{round(self.pressure)} mbar"),
            make_line('Nuvolosità', f"{round(self.cover, 1)}%"),
            make_line('Base delle nubi', f"{self.cloud_base} m" if self.cloud_base is not None else '--'),
            make_line('Visibilità', f"{self.visibility} km",
                      f"{wind} {wind_gusts}"),
            make_line('Levar del Sole', self.sunrise.strftime('%H:%M'), wind_description[0]),
            make_line('Tramonto', self.sunset.strftime('%H:%M'), wind_description[1])
        )
        return f"${{image $HOME/.conky/climacell/imgs/{img}.png -p 72,{voffset} -s 80x80}}" \
               f"${{image $HOME/.conky/climacell/imgs/{wind_img}.png -p 54,{voffset + 83} -s 50x50}}" \
               '\n'.join(weather_info)


class Forecast(ClimaCellWeather):
    def __init__(self, weather: dict):
        super().__init__(weather)
        self.precipitation = weather['precipitation']['value']
        self.probability = weather['precipitation_probability']['value']

    @staticmethod
    def format_line(hoffset, hour, icon, cloud_base, precipitation, probability, wind, temperature):
        return f"${{goto {hoffset}}}{hour}{icon}" \
               f"${{goto {hoffset + 47}}}{cloud_base}" \
               f"${{goto {hoffset + 85}}}{precipitation}" \
               f"${{goto {hoffset + 125}}}{probability}" \
               f"${{goto {hoffset + 162}}}{wind}" \
               f"${{goto {hoffset + 197}}}{temperature}"

    def to_string(self, hoffset):
        hour = f"{self.timestamp.hour:02}"
        icon = ICONS[self.code.replace('_light', '').replace('_heavy', '').replace('drizzle', 'rain')]
        if type(icon) == list:
            icon = icon[self.is_night()]
        cloud_base = (format_number(self.cloud_base, 3) + 'km') if self.cloud_base is not None else '  --'
        precipitation_mm = self.precipitation > 0.05
        precipitation = (format_number(self.precipitation, 0 if precipitation_mm else -3) +
                         ('mm' if precipitation_mm else 'um')) \
            if self.precipitation else '  --'
        probability = format_number(self.probability, 0, 3, 100) + '%' if self.probability else '  --'
        wind = str(int(round(self.wind))).rjust(2, ' ')
        direction = "${font Monospace\\ Regular:size=9}" + \
                    chr(ord(DIRECTIONS[int(self.wind_direction / 2)]) + self.gusts * 0x40) + \
                    "${font}"
        temperature = str(int(round(self.feels_like))).rjust(2, ' ') + '°'
        # f"${{image $HOME/.conky/climacell/black/{self.code}.png -p {px},{py} -s {width}x{height}}}" \
        return self.format_line(hoffset,
                                f"h{hour}",
                                f"${{voffset -4}}${{font Weather\\ Icons:Regular:size=11}}"
                                f"{chr(icon)}"
                                f"${{font}}${{voffset -1}}",
                                cloud_base,
                                precipitation,
                                probability,
                                wind + direction,
                                temperature
                                )


def daily_info(weather):
    date = format_day(get_timestamp(weather['observation_time']['value']))
    img = IMGS[weather['weather_code']['value']]
    if type(img) == list:
        img = img[0]
    return date, img


current = CurrentWeather(current)
hourly = [Forecast(hourly[i]) for i in range(48)]
daily_index = next(i for i in range(10)
                   if get_timestamp(daily[i]['observation_time']['value']).day == (current.timestamp.day + 2))
daily = [(offset, *daily_info(weather))
         for offset, weather in zip(range(35, 450, 113), daily[daily_index:daily_index + 4])]

print(current.to_string(20))
print("${font Ubuntu\\ Mono:normal:size=7}${voffset -2}${goto 235}climacell.co"
      f"${{alignr}}${{offset 14}}{warning}aggiornato {current.timestamp.strftime('%H:%M:%S')}"
      "$font${goto 10}${voffset 1}${color3}${hr}$color")
print(f"${{color1}}"
      f"${{goto 88}}{format_day(current.timestamp).upper()}"
      f"${{goto 319}}{format_day(current.timestamp + timedelta(days=1)).upper()}${{color}}")
print("".join(Forecast.format_line(offset, "Ora", "", "Nubi", "Prec", "Prob", " V ", " T ") for offset in [10, 240]))
for i in range(24):
    print(f"${{color3}}{hourly[i].to_string(10)}${{goto 230}}|{hourly[i + 24].to_string(240)}${{color}}")
print("${voffset -5}${goto 10}${color3}${hr}$color")
print("".join([f"${{goto {offset}}}{date}" for offset, date, _ in daily]))
print("".join(
    [f"${{image $HOME/.conky/climacell/imgs/{img}.png -p {offset - 3},585 -s 50x50}}" for offset, _, img in daily]))
