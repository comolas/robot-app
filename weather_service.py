import requests
import os

class WeatherService:
    def __init__(self, api_key: str, city: str = "Istanbul", country: str = "TR"):
        self.api_key = api_key
        self.city = city
        self.country = country
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"
    
    def get_weather(self) -> str:
        """Hava durumu bilgisini al"""
        try:
            params = {
                "q": f"{self.city},{self.country}",
                "appid": self.api_key,
                "units": "metric",
                "lang": "tr"
            }
            
            response = requests.get(self.base_url, params=params)
            data = response.json()
            
            if response.status_code == 200:
                temp = data["main"]["temp"]
                feels_like = data["main"]["feels_like"]
                humidity = data["main"]["humidity"]
                description = data["weather"][0]["description"]
                
                weather_info = f"""HAVA DURUMU BİLGİSİ ({self.city})

Sıcaklık: {temp}°C
Hissedilen: {feels_like}°C
Nem: {humidity}%
Durum: {description.capitalize()}"""
                
                return weather_info
            else:
                return "Hava durumu bilgisi alınamadı."
                
        except Exception as e:
            return f"Hava durumu servisi hatası: {str(e)}"
