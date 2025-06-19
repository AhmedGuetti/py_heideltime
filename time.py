#!/usr/bin/env python3
from python_heidelTime import HeidelTime



if __name__ == "__main__":
    heideltime = HeidelTime(config="hconfig.json")
 
    # Parse text
    try:
        result = heideltime.parse("Today is the 12 mars i have go to the hostpital to get a traitement, because yesterday i ate the wrong stuff, since i wasn't\
        right, Now we are the 3/16/2025 and am still getting the same medicament ")
        print(result)
    except Exception as e:
        print(f"Error: {e}")
