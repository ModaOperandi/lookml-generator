PRODUCTS_KEY = 'products'

SRX_MODE = 'srx'
TABLE_MODE = 'table'

MODES = (SRX_MODE, TABLE_MODE)

class LookMLProcessor:
    def __init__(self, input_json, config):
        self.input = input_json
        self.output = {}
        self.config = config
        self.table_field = None

        # Ensure we have a proper mode
        mode = self.config.get('operationMode')
        if not mode or mode not in MODES:
            print('No valid operationMode was specified in the config.', file=sys.stderr)
            raise ConverterException('Invalid mode')

        ## Build some templates
        self.prepare_templates()

    def prepare_templates(self):
        try:
            # Prepare all templates
            stream = open(self.config.get('propertyTemplate'))
            self.property_template = stream.read()
            stream.close()

            stream = open(self.config.get('viewTemplate'))
            self.view_template = stream.read()
            stream.close()

            subview_template_filename = self.config.get('subviewTemplate')
            if subview_template_filename:
                stream = open(subview_template_filename)
                self.subview_template = stream.read()
                stream.close()
        except FileNotFoundError as e:
            print('Property template missing: {}'.format(e.message), file=sys.stderr)
            raise ConverterException(e.message)
        except Exception as e:
            print('There was an error building templates: {}'.format(e.message), file=sys.stderr)
            return ConverterException(e.message)

    def build_context(self, context, suffix):
        for prop in context:
            if isinstance(context[prop], dict):
                self.build_context(context[prop], '{}{}_'.format(suffix, prop))
                continue

            created_prop = self.create_property(context[prop], '{}{}'.format(suffix, prop))
            if created_prop:
                self.output[prop] = created_prop

    '''
    Builds the product-joinable subview
    '''
    def build_products(self, products):
        lookml_products = {}

        # Build keys & stuff
        for product in products:
            for key in product:
                if not key in lookml_products:
                    lookml_products[key] = LookMLProduct(key, isinstance(product[key], str))

        # Build JSON table
        json_select_fields = ',\n       '.join([lookml_products[key].select_field for key in lookml_products])
        products_output = '\n'.join([self.create_property(None, prop) for prop in lookml_products])

        table = self.config.get('table')

        processed_subview = self.subview_template \
            .replace('{{properties}}', products_output) \
            .replace('{{jsonSelectFields}}', json_select_fields) \
            .replace('{{lookerView}}', 'site_{}'.format(table.lower())) \
            .replace('{{lookerViewSuffix}}', 'pid') \
            .replace('{{parentField}}', 'products') \
            .replace('{{tableName}}', table.upper())

        self.subview = processed_subview

    def convert_table_type(self, type):
        if type == 'DATE':
            return 'date'
        elif type in (
            'TIMESTAMP_LTZ', 'DATETIME', 'TIMESTAMP_NTZ',
            'TIME', 'TIMESTAMP_TZ', 'TIMESTAMP'
        ):
            return 'date_time'
        elif type == 'BOOLEAN':
            return 'yesno'
        elif type in (
            'BIGINT', 'FLOAT8', 'INT', 'DECIMAL', 'INTEGER',
            'DOUBLE', 'NUMBER', 'DOUBLE', 'PRECISION', 'NUMERIC',
            'FLOAT', 'REAL', 'FLOAT4', 'SMALLINT'
        ):
            return 'number'

        return 'string'

    def create_property(self, prop, prop_name, type=None):
        if prop_name == PRODUCTS_KEY:
            self.build_products(prop)
            return None

        if not type:
            type = 'string' if isinstance(prop, str) else 'number'

        return self.property_template \
            .replace('{{lookerField}}', prop_name.lower()) \
            .replace('{{tableField}}', prop_name.upper()) \
            .replace('{{type}}', type)

    '''
    Creates the main view for the table (SRX)
    '''
    def create_view_srx(self):
        table = self.config.get('table')
        if not table:
            raise ConverterException('No table prop! Aborting...')

        processed_props = '\n'.join([self.output[prop] for prop in self.output])
        processed_view = self.view_template \
            .replace('{{properties}}', processed_props) \
            .replace('{{lookerView}}', 'site_{}'.format(table.lower())) \
            .replace('{{tableName}}', table.upper())

        self.view = processed_view

    '''
    Creates the main view for the table (Table)
    '''
    def create_view_table(self):
        processed_props = '\n'.join([self.output[prop] for prop in self.output])
        processed_view = self.view_template \
            .replace('{{fields}}', processed_props) \
            .replace('{{lookerView}}', 'table_{}'.format(self.table_field.lower())) \
            .replace('{{tableName}}', self.table_field)

        self.view = processed_view

    def save_files(self):
        if not hasattr(self, 'view'):
            raise ConverterException('No view has been created.')

        table_view = self.table_field.lower() if self.table_field else self.config.get('table').lower()

        format_file_str = 'site_{}.{}' if self.config['operationMode'] == SRX_MODE else 'table_{}.{}'
        view_file = format_file_str.format(table_view, self.config['outputFileExtension'])

        write_stream = open(view_file, 'w')
        print(self.view, file=write_stream)
        write_stream.close()

        print('{} written successfully.'.format(view_file))

        if hasattr(self, 'subview'):
            subview_file = 'site_{}_pid.{}'.format(table_view, self.config['outputFileExtension'])

            write_stream = open(subview_file, 'w')
            print(self.subview, file=write_stream)
            write_stream.close()

            print('{} written successfully.'.format(subview_file))

    def process_srx(self):
        # Build props
        for key in self.input:
            if key == 'properties':
                for prop in self.input[key]:
                    created_prop = self.create_property(self.input[key][prop], prop)
                    if created_prop:
                        self.output[prop] = created_prop

            elif key == 'context':
                self.build_context(self.input[key], 'context_')

        # Create main view
        self.create_view_srx()

        # Save files
        self.save_files()

    def process_table(self):
        for field in self.input:
            created_prop = self.create_property(None, field['COLUMN_NAME'], self.convert_table_type(field['DATA_TYPE']))
            if created_prop:
                self.output[field['COLUMN_NAME']] = created_prop

            if not self.table_field:
                self.table_field = field['TABLE_NAME']

        # Create main view
        self.create_view_table()

        # Save files
        self.save_files()


class LookMLProduct:
    def __init__(self, key, is_string):
        self.key = key

        self.select_field = '''REPLACE(F.VALUE:{}, '"', '') AS {}'''.format(key, key.upper()) \
            if is_string else 'F.VALUE:{} AS {}'.format(key, key.upper())
        self.table_field = key.upper()

class ConverterException(Exception):
    pass
