def generate_demo_sentence(demo):
    """
    Generate a sentence describing the demonstration schedule in Finnish.

    Parameters
    ----------
    demo : dict
        Dictionary containing the demonstration schedule information.

    Returns
    -------
    str
        The generated sentence in Finnish.
    """
    sentence = "Toistuu "

    # Fetch frequency and repeat schedule details
    repeat_schedule = demo.get("repeat_schedule", {})
    frequency = repeat_schedule.get("frequency")
    end_date = repeat_schedule.get("end_date")

    # Define weekdays and nth weekday in Finnish
    weekdays = {
        "monday": "maanantaina",
        "tuesday": "tiistaina",
        "wednesday": "keskiviikkona",
        "thursday": "torstaina",
        "friday": "perjantaina",
        "saturday": "lauantaina",
        "sunday": "sunnuntaina",
    }
    nth_weekdays = {
        "first": "ensimmäisenä",
        "second": "toisena",
        "third": "kolmantena",
        "fourth": "neljäntenä",
        "last": "viimeisenä",
    }

    if frequency == "daily":
        sentence += "päivittäin."
    elif frequency == "weekly":
        weekday = repeat_schedule.get("weekday")
        weekday_name = weekdays.get(weekday, "")
        if weekday_name:
            sentence += f"joka viikko {weekday_name}."
        else:
            sentence += "viikoittain."
    elif frequency == "monthly":
        monthly_option = repeat_schedule.get("monthly_option")
        if monthly_option == "day_of_month":
            day_of_month = repeat_schedule.get("day_of_month", "")
            sentence += f"joka kuukauden {day_of_month}. päivä."
        elif monthly_option == "nth_weekday":
            nth_weekday = repeat_schedule.get("nth_weekday", "")
            weekday_of_month = repeat_schedule.get("weekday_of_month", "")
            nth_weekday_name = nth_weekdays.get(nth_weekday, "")
            weekday_name = weekdays.get(weekday_of_month, "")
            if nth_weekday_name and weekday_name:
                sentence += f"joka kuukauden {nth_weekday_name} {weekday_name}."
            else:
                sentence += "kuukausittain."
    elif frequency == "yearly":
        sentence += "vuosittain."

    if end_date and not "9999" in end_date:
        sentence = sentence.rstrip(".") + f", päättyen {end_date}."

    return sentence
