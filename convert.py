import json
import sys
from lookml_processor import LookMLProcessor, ConverterException

def load_config():
    try:
        config_stream = open('config.json')
    except FileNotFoundError as e:
        print('No config.json file found.', file=sys.stderr)
        return None
    except Exception as e:
        print('There was an error reading the config json.', file=sys.stderr)
        return None

    config = json.load(config_stream)
    config_stream.close()
    return config

def load_input_json(config):
    try:
        input_stream = open(config['inputFile'])
    except FileNotFoundError as e:
        print('The inputFile in config.json was not found.', file=sys.stderr)
        return None
    except Exception as e:
        print('There was an error reading the input json.', file=sys.stderr)
        return None

    input_json = json.load(input_stream)
    input_stream.close()
    return input_json

def build_props():
    pass

def main():
    # Import the config file
    config = load_config()
    if not config:
        return

    # Load the input json
    input_json = load_input_json(config)
    if not input_json:
        return

    # Create the processor
    try:
        processor = LookMLProcessor(input_json, config)

        # Process the data!
        processor.process()

        print('LookML files written successfully.')
    except ConverterException as e:
        print('Error in processing.', file=sys.stderr)

main()
