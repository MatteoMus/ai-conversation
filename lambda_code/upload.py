import json
import boto3
import logging
import io
import hashlib
import http.client
import re
from xml.etree import ElementTree as ET
import uuid
from time import sleep

logging.basicConfig(format='[%(asctime)s] {%(filename)s:%(lineno)d} %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
polly_client = boto3.client('polly')
bucket = 'ai-conversation-frontend'
dst_prefix = 'inputs/'

def agent(input: str, agent: dict) -> str:
   
   agentResponse = bedrock_agent_runtime_client.invoke_agent(
        inputText=f"The topic to announce is: {input}",
        agentId=agent['agentId'],
        agentAliasId=agent['agentAliasId'],
        sessionId=str(uuid.uuid4()),
        enableTrace=False, 
        endSession=False
   )
   logger.info(f"AGENT RESPONSE: {agentResponse}")

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

        conn.request("POST", f"/v1/text-to-speech/{agent['voice_elevenlabs']}?output_format=mp3_44100_128", payload, headers)

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

def audio_push_s3(filename: str, audio_name: str):
    with open(filename, 'rb') as data:
        s3_client.upload_fileobj(data, bucket, f"{dst_prefix}{audio_name}")

def generate_default_announce(topic: str, agent: dict, content_hash: str) -> str:
   default_announce = f"<speak>Ladies and gentlemen, <break time='300ms'/> welcome! <break time='300ms'/> I’m your host, and today our guests will discuss about: {topic}. <break time='300ms'/> Enjoy the debate!</speak>"
   audio_name = f"{content_hash}.mp3"
   response_audio = synthesize(default_announce, agent, audio_name)
   audio_push_s3(response_audio, audio_name)

def generate_announce(AnnouncerAgent, SsmlAgent, content, content_hash):
   try:
      response_text = agent(content, AnnouncerAgent)
      logger.info(f"RESPONSE TEXT: {response_text}")
   except Exception as e:
      logger.error(f"Error in announce generation: {e}")
      return {
         "validation": False,
         "response_error": str(e),
         "response_text": ""
      }

   # Add SSML tags
   try:
      response_text = agent(response_text, SsmlAgent)
      logger.info(f"RESPONSE TEXT: {response_text}")
   except Exception as e:
      logger.error(f"Error in SSML tags generation: {e}")
      return {
         "validation": False,
         "response_error": str(e),
         "response_text": ""
      }

   # get <speak></speak> content
   speak_text = str(extract_speak_content(response_text))
   logger.error(f"SPEAK TEXT: {speak_text}")

   # check <speak></speak> content
   if speak_text is None:
      logger.error("No text included in <speak> and </speak> tags.")
      return {
         "validation": False,
         "response_error": "No text included in <speak> and </speak> tags.",
         "response_text": response_text
      }

   # check SSML
   ssml_is_valid, ssml_validation_errors = validate_ssml(speak_text)
   if not ssml_is_valid:
      logger.error(f"SSML validation failed: {ssml_validation_errors}")
      return {
         "validation": False,
         "response_error": ssml_validation_errors,
         "response_text": response_text
      }

   # audio from text generation
   # save audio to S3
   try:
      audio_name = f"{content_hash}.mp3"
      response_audio = synthesize(speak_text, AnnouncerAgent, audio_name)
      audio_push_s3(response_audio, audio_name)
   except Exception as e:
      logger.error(f"Error in audio generation: {e}")
      return {
         "validation": False,
         "response_error": str(e),
         "response_text": response_text
      }
   
   #If everything is ok
   return {
      "validation": True,
      "response_error": "",
      "response_text": response_text,
   }

def lambda_handler(event, context):
   logger.info(f"Event: {event}")
   upload_file = event['Records'][0]['s3']['object']['key']

   AnnouncerAgent = {
      "agentId": "BWLYTYTY4U",
      "agentAliasId": "COESFN5CQI",
      "voice": "Joanna",
      "voice_elevenlabs": ""
   }

   SsmlAgent = {
      "agentId": "EMCMWQNLST",
      "agentAliasId": "NT9HMO4MKC",
   }
   
   #generate_inputs(upload_file)
   obj = s3_client.get_object(Bucket=bucket, Key=upload_file)
   body = obj['Body'].read().decode('utf-8')

  # Process and upload
   for idx, line in enumerate(body.splitlines(), start=1):
      content = line.strip()
      if content:
         content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
         s3_key = f"{dst_prefix}{content_hash}.txt"
         fileobj = io.BytesIO(content.encode('utf-8'))
         s3_client.upload_fileobj(fileobj, bucket, s3_key)
         logger.info(f"Uploaded line {idx} to s3://{bucket}/{s3_key}")

   logger.info("Input file processed. Starting announce generation...")

   #Generate announce
   for idx, line in enumerate(body.splitlines(), start=1):
      content = line.strip()
      if content:
         content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
         announce_generation_failure_counter = 0
         while announce_generation_failure_counter < 2:
            result = generate_announce(AnnouncerAgent, SsmlAgent, content, content_hash)
            if result["validation"]:
               logger.info(f"Successfully processed line {idx}: {result['response_text']}")
               break
            else:
               logger.error(f"Failed to process line {idx}: {result['response_error']}")
               announce_generation_failure_counter += 1
         
         if announce_generation_failure_counter == 2:
            logger.error(f"Failed to process line {idx} after 2 attempts.")
            # Generate default announce
            generate_default_announce(content, AnnouncerAgent, content_hash)
            logger.info(f"Default announce generated for line {idx}.")
      
      sleep(2)

   logger.info("Announce generation completed.")

   return {
      'statusCode': 200,
      'body': json.dumps('Processing complete.')   
   }

if __name__ == "__main__":
  event = {  
   "Records":[  
      {  
         "s3":{  
            "object":{  
               "key":"uploads/test.txt"
            }
         }
      }
   ]
}
  context = None
  lambda_handler(event, context)