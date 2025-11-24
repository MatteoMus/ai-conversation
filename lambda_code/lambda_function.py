import json
import boto3
import logging
import io
import re
import os
from xml.etree import ElementTree as ET
import http.client

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.ERROR)
logger = logging.getLogger(__name__)
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
polly_client = boto3.client('polly')
s3_client = boto3.client('s3')
elevenlabsa_api_key = os.environ['elevenlabs_api_key']

def retrieve_knowledge(knowledge_base_id, input, agent_abstract, conversation_params):

    try:
        abstract = agent(input, agent_abstract, conversation_params)
        logger.error(f"Abstract for knowledge base: {abstract}")
    except Exception as e:
        logger.error(f"Error generating abstract: {e}")
        abstract = ""

    try:
      response = bedrock_agent_runtime_client.retrieve(
          knowledgeBaseId=knowledge_base_id,
          retrievalQuery={
            'text': abstract
          },
          retrievalConfiguration={
              "vectorSearchConfiguration": {
                "numberOfResults": 5    
              }
              
          }
      )
      logger.error(f"Retrived knowledge: {response}")
      texts = [item["content"]["text"] for item in response["retrievalResults"]]
      all_text = "\n\n".join(texts)

      return all_text
    
    except Exception as e:
      logger.error(f"Error retrieving knowledge: {e}")
      return "Error retrieving knowledge"

def agent_with_knowledge(input: str, agent: dict, conversation_params: dict, agent_abstract: dict) -> str:
    
    agentResponse = bedrock_agent_runtime_client.invoke_agent(
        inputText=input,
        agentId=agent['agentId'],
        agentAliasId=agent['agentAliasId'],
        sessionId=conversation_params['session_id'],
        enableTrace=conversation_params['enable_trace'], 
        endSession=conversation_params['end_session'],
        promptCreationConfigurations=conversation_params['prompt_creation_configurations'],
        sessionState={
            "promptSessionAttributes": {
                "context": retrieve_knowledge(agent['knowledgeBaseId'], input, agent_abstract, conversation_params)
            }
        }
    )
    logger.error(f"AGENT RESPONSE: {agentResponse}")

    event_stream = agentResponse['completion']
    agent_answer = ""
    try:
        for event in event_stream:        
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer += data.decode('utf8')  # Accumulate response chunks
            elif 'trace' in event:
                logger.error(json.dumps(event['trace'], indent=2))
            else:
                raise Exception("Unexpected event.", event)
    except Exception as e:
        raise Exception("Unexpected event.", e)

    return agent_answer.strip()

#with no knowledge
def agent(input: str, agent: dict, conversation_params: dict) -> str:
    agentResponse = bedrock_agent_runtime_client.invoke_agent(
        inputText=input,
        agentId=agent['agentId'],
        agentAliasId=agent['agentAliasId'],
        sessionId=conversation_params['session_id'],
        enableTrace=conversation_params['enable_trace'], 
        endSession=conversation_params['end_session'],
        promptCreationConfigurations=conversation_params['prompt_creation_configurations'],
    )
    logger.error(f"AGENT RESPONSE: {agentResponse}")

    event_stream = agentResponse['completion']
    agent_answer = ""
    try:
        for event in event_stream:        
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer += data.decode('utf8')  # Accumulate response chunks
            elif 'trace' in event:
                logger.error(json.dumps(event['trace'], indent=2))
            else:
                raise Exception("Unexpected event.", event)
    except Exception as e:
        raise Exception("Unexpected event.", e)

    return agent_answer.strip()

def get_stop_from_tags(input_str):
    # Define the regex pattern to match content inside <STOP> and </STOP> tags
    pattern = r"<STOP>(.*?)</STOP>"
    match = re.search(pattern, input_str, re.IGNORECASE)
    if match:
        # Extract the content inside the tags
        content = match.group(1).strip().lower()
        # Return True if the content is "true", otherwise False
        return content == "true"
    else:
        # Raise an error if <STOP> tags are not found
        raise ValueError("Input does not contain valid <STOP> tags.")

def text_push_s3(body: str, bucket: str, text_name: str, UUID: str):
    s3_client.put_object(Body=body, Bucket=bucket, Key=f"outputs/{UUID}/{text_name}")

def extract_reasoning(text: str) -> str:
    # Try to find reasoning tag
    reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', text, re.DOTALL)
    if reasoning_match:
        return reasoning_match.group(1).strip()
    
    # If no reasoning tag, extract everything outside <STOP>...</STOP>
    outside_text = re.sub(r'<STOP>.*?</STOP>', '', text, flags=re.DOTALL).strip()
    return outside_text

def synthesize(body: str, agent: dict, audio_name: str):
    filename = f"/tmp/{audio_name}"

    if "voice_elevenlabs" in agent and agent["voice_elevenlabs"] != "":
        conn = http.client.HTTPSConnection("api.elevenlabs.io")

        payload = json.dumps({
            "text": body,
            "model_id": "eleven_multilingual_v2"
        })

        headers = {
            'xi-api-key': 'sk_01dcae060a644561ae2b4feaa0007090c5ad869d4299eb8d',
            'Content-Type': 'application/json'
        }

        conn.request("POST", f"/v1/text-to-speech/{agent["voice_elevenlabs"]}?output_format=mp3_44100_128", payload, headers)

        res = conn.getresponse()
        data = res.read()

        # Save the mp3 response content to a file
        with open(filename, "wb") as f:
            f.write(data)

        return filename
    else:
        response = polly_client.synthesize_speech(
            Text=body,
            OutputFormat='mp3',
            Engine="neural",
            TextType='ssml',
            VoiceId=agent['voice']
        )
        
        if 'AudioStream' in response:
            with open(filename, 'wb') as file:
                file.write(response['AudioStream'].read())        
            return filename
        else:
            raise Exception("Could not synthesize speech from text.")

def audio_push_s3(filename: str, bucket: str, audio_name: str, UUID: str):
    with open(filename, 'rb') as data:
        s3_client.upload_fileobj(data, bucket, f"outputs/{UUID}/{audio_name}")

def text_push_s3(body: str, bucket: str, text_name: str, UUID: str):
    s3_client.put_object(Body=body, Bucket=bucket, Key=f"outputs/{UUID}/{text_name}")

def extract_speak_content(input_text):
    match = re.search(r"<speak>(.*?)</speak>", input_text, re.DOTALL)
    if match:
        return f"<speak>{match.group(1).strip()}</speak>"
    return None

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

def lambda_handler(event, context):
    #print input
    logger.error(f"EVENT: {event}")

    #vars
    s3_bucket_name = os.environ['s3_bucket']
    audio_name = str(event['Turn']) + ".mp3"
    text_name = str(event['Turn']) + ".txt"

    #LLM text generation
    try:
        if "knowledgeBaseId" in event['Speaker']:
            response_text = agent_with_knowledge(event['Input'], event['Speaker'], event['ConversationParams'], event['Abstract'])
        else:
            response_text = agent(event['Input'], event['Speaker'], event['ConversationParams'])
        logger.error(f"RESPONSE TEXT: {response_text}")
    except Exception  as e:
        logger.error(f"Error in text generation: {e}")
        return {
            "validation": False,
            "response_error": str(e),
            "response_text": ""
        }

    #SSML tags generation
    try:
        response_text = agent(response_text, event['Ssml'], event['ConversationParams'])
        logger.error(f"RESPONSE TEXT: {response_text}")
    except Exception  as e:
        logger.error(f"Error in SSML tags generation: {e}")
        return {
            "validation": False,
            "response_error": str(e),
            "response_text": ""
        }


    #save text to S3
    text_push_s3(response_text, s3_bucket_name, text_name, event['UUID'])

    #get <speak></speak> content
    speak_text = str(extract_speak_content(response_text))
    logger.error(f"SPEAK TEXT: {speak_text}")

    #check <speak></speak> content
    if speak_text is None:
        logger.error("No text included in <speak> and </speak> tags.")
        return {
            "validation": False,
            "response_error": "No text included in <speak> and </speak> tags.",
            "response_text": response_text
        }
    
    #check SSML
    ssml_is_valid, ssml_validation_errors = validate_ssml(speak_text)
    if not ssml_is_valid:
        logger.error(f"SSML validation failed: {ssml_validation_errors}")
        return {
            "validation": False,
            "response_error": ssml_validation_errors,
            "response_text": response_text
        }
    
    #audio from text generation
    #save audio to S3
    try:
        response_audio = synthesize(speak_text, event['Speaker'], audio_name)
        audio_push_s3(response_audio, s3_bucket_name, audio_name, event['UUID'])
    except Exception as e:
        logger.error(f"Error in audio generation: {e}")
        return {
            "validation": False,
            "response_error": str(e),
            "response_text": response_text
        }

    #END
    logger.error(f"TURN {event['Turn']} SUCCESS")
    return {
            "validation": True,
            "response_error": "",
            "response_text": speak_text
        }