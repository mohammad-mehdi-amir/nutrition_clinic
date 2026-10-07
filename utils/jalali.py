import jdatetime


def jalali_to_gregorian(date_string):
    """
    Convert Jalali date string:
    1405-07-15
    or
    1405/07/15

    to Python Gregorian date.
    """

    if not date_string:
        return None

    date_string = date_string.replace("/", "-")

    year, month, day = map(
        int,
        date_string.split("-")
    )

    return jdatetime.date(
        year,
        month,
        day
    ).togregorian()


def gregorian_to_jalali(date):
    """
    Convert Python Gregorian date to Jalali date.
    """

    if not date:
        return None

    return jdatetime.date.fromgregorian(
        date=date
    )


def format_jalali(date, separator="/"):
    """
    Convert Gregorian date to:
    1405/07/15
    """

    jalali_date = gregorian_to_jalali(date)

    if not jalali_date:
        return ""

    return jalali_date.strftime(
        f"%Y{separator}%m{separator}%d"
    )