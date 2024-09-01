with open("cities.txt", encoding="utf-8") as f:
    cities = f.readlines()
    
print(list([city.replace("\n", "") for city in cities]))