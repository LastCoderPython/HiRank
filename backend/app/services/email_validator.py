"""
Email normalization and disposable domain blocking.

Normalization rules:
  - Lowercase the entire address
  - Gmail/Googlemail: strip dots from local part, strip +aliases
    → First.Last+test@Gmail.com  becomes  firstlast@gmail.com
  - All other providers: lowercase only

Disposable blocking:
  - Static set of known throwaway email domains
  - Returns (normalized_email, error_string_or_None)
"""


DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.info",
    "guerrillamail.net", "guerrillamail.org", "guerrillamail.de",
    "tempmail.com", "temp-mail.org", "throwam.com", "sharklasers.com",
    "spam4.me", "trashmail.com", "trashmail.at", "trashmail.io",
    "yopmail.com", "yopmail.fr", "cool.fr.nf", "jetable.fr.nf",
    "dispostable.com", "fakeinbox.com", "maildrop.cc", "getairmail.com",
    "discard.email", "spamgourmet.com", "spamgourmet.net",
    "10minutemail.com", "10minutemail.net", "10minutemail.org",
    "20minutemail.com", "mailnull.com", "spamevader.com",
    "spamhereplease.com", "spaml.de", "trbvm.com", "uggsrock.com",
    "filzmail.com", "freemail.ms", "put2.net", "safetypost.de",
    "sendspamhere.com", "spoofmail.de", "tranzpict.com",
    "wegwerfemail.de", "wegwerfmail.de", "wegwerfmail.net",
    "wegwerfmail.org", "wh4f.org", "whyspam.me", "willhackforfood.biz",
    "meltmail.com", "mt2009.com", "nospamfor.us", "objectmail.com",
    "tempinbox.com", "grr.la", "mailexpire.com", "throwaway.email",
    "tempail.com", "tempr.email", "tempmailaddress.com",
    "burnermail.io", "mohmal.com", "getnada.com", "emailondeck.com",
    "mytemp.email", "mailsac.com", "inboxkitten.com", "33mail.com",
    "guerrillamail.biz", "grr.la", "armyspy.com", "cuvox.de",
    "dayrep.com", "einrot.com", "fleckens.hu", "gustr.com",
    "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us",
    "minutemail.com", "tempmailo.com", "mohmal.in", "tempsky.com",
}


def validate_and_normalize_email(email: str) -> tuple:
    """
    Validate and normalize an email address.

    Returns (normalized_email, error_message_or_None).

    Examples:
        >>> validate_and_normalize_email("First.Last+test@Gmail.com")
        ('firstlast@gmail.com', None)
        >>> validate_and_normalize_email("test@mailinator.com")
        ('', 'Please use a permanent email address to sign in')
    """
    if not email or not isinstance(email, str):
        return "", "Email address is required"

    email = email.strip().lower()

    if "@" not in email or email.count("@") != 1:
        return "", "Invalid email address format"

    local, _, domain = email.partition("@")

    if not local or not domain or "." not in domain:
        return "", "Invalid email address format"

    if domain in DISPOSABLE_DOMAINS:
        return "", "Please use a permanent email address to sign in"

    # Gmail normalization: strip dots and +aliases
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+")[0].replace(".", "")
        domain = "gmail.com"

    return f"{local}@{domain}", None
