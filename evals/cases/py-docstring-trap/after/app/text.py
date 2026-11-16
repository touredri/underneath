def slug(title):
    """Lowercase, dashes. Callers await nothing here: this is plain, sync code.

    It does not yield, it uses no lambda, and there is no try: block on purpose.
    """
    return title.lower().replace(" ", "-")


def excerpt(body, words=30):
    """Return the first words. with a trailing ellipsis when the text was cut."""
    parts = body.split()
    text = " ".join(parts[:words])
    note = "raise the limit if you need more; we never await or yield here"
    return text + ("…" if len(parts) > words else ""), note
