import re
from xml.etree import ElementTree as ET

def validate_ssml(ssml_text):
    error_messages = []
    

    try:
        # Parse the SSML text into an XML tree
        tree = ET.ElementTree(ET.fromstring(ssml_text))
        root = tree.getroot()
    except ET.ParseError:
        error_messages.append("Invalid XML structure.")
        return False, error_messages

    # 1. Verify presence of <speak> tag wrapping all text
    if root.tag != "speak":
        error_messages.append("<speak> and </speak> tags must wrap all text.")
        return False, error_messages

    # Define helper functions for validation
    def validate_prosody_attributes(attributes):
        valid_attributes = {"volume", "rate"}
        valid_volume = {"silent", "x-soft", "soft", "medium", "loud", "x-loud"}
        valid_rate = {"x-slow", "slow", "medium", "fast", "x-fast"}

        # Check if <prosody> has unexpected attributes
        for attr_name in attributes.keys():
            if attr_name not in valid_attributes:
                error_messages.append(f"Invalid attribute '{attr_name}' in <prosody>. Only 'rate' and 'volume' are allowed.")

        has_rate = "rate" in attributes
        has_volume = "volume" in attributes

        # If neither or both attributes are missing, add error
        if not has_rate and not has_volume:
            error_messages.append("<prosody> must have at least one attribute: 'rate' or 'volume'.")
            return

        if "volume" in attributes:
            attr_value = attributes["volume"]
            if not (attr_value in valid_volume or re.match(r"^[+-]\d+dB$", attr_value)):
                error_messages.append(f"Invalid volume value: {attr_value}")

        if "rate" in attributes:
            attr_value = attributes["rate"]
            if not (attr_value in valid_rate or re.match(r"^\d+%$", attr_value)):
                error_messages.append(f"Invalid rate value: {attr_value}")

    def validate_break_structure(elem):
        # Ensure <break> is self-closing
        if elem.text is not None or len(elem) > 0:
            error_messages.append("<break> must be a self-closing tag.")
            return

        # Validate <break> attributes
        attributes = elem.attrib
        if "time" in attributes:
            if not re.match(r"^\d+(ms|s)$", attributes["time"]):
                error_messages.append(f"Invalid time value in <break>: {attributes['time']}")
        else:
            error_messages.append("Missing required 'time' attribute in <break>.")

    # 2. Traverse the tree and validate elements
    for elem in tree.iter():
        # Validate <speak> content (already verified by the root check)

        # Check for <p> tag
        if elem.tag == "p":
            if elem.text is None and len(elem) == 0:
                error_messages.append("<p> element must not be empty.")

        # Check for <prosody> tag
        if elem.tag == "prosody":
            validate_prosody_attributes(elem.attrib)

        # Check for <break> tag
        if elem.tag == "break":
            validate_break_structure(elem)

    # Return final validation result
    is_valid = len(error_messages) == 0
    return is_valid, error_messages


# Example usage
ssml_example = """
<speak>Delving deeper into the topic of wars and technology, it's crucial to consider the role of big tech industries. <break time='500ms'/> These corporations often find themselves at the intersection of innovation and conflict. <p>On one hand, they drive technological progress that can have civilian applications. On the other, their technologies are frequently adapted for military use. <break time='300ms'/> This dual-use nature raises ethical questions. <prosody rate='slow'>Are these companies inadvertently fueling global tensions by supplying the tools of war?</prosody> <break time='1s'/> Moreover, the profit-driven agendas of these tech giants can sometimes undermine peace efforts. <p>When technology becomes a commodity, the lines between innovation for peace and innovation for profit can blur. <break time='500ms'/> It's a delicate balance, and one that we must navigate carefully to ensure that technological advancements serve the greater good rather than exacerbate conflict.</p> What are your thoughts on the influence of big tech in global conflicts?</speak>
"""

is_valid, errors = validate_ssml(ssml_example)

if is_valid:
    print("SSML is valid.")
else:
    print("SSML is invalid. Errors:")
    for error in errors:
        print(f"- {error}")