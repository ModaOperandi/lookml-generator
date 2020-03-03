PRODUCTS_KEY = 'products'

class LookMLProcessor:
    def __init__(self, input_json, config):
        self.input = input_json
        self.output = {}
        self.config = config

        ## Build some templates
        self.prepare_templates()

    def prepare_templates(self):
        try:
            stream = open(self.config.get('propertyTemplate'))
            self.property_template = stream.read()
            stream.close()

            stream = open(self.config.get('viewTemplate'))
            self.view_template = stream.read()
            stream.close()

            stream = open(self.config.get('subviewTemplate'))
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

    def create_property(self, prop, prop_name):
        if prop_name == PRODUCTS_KEY:
            self.build_products(prop)
            return None

        return self.property_template \
            .replace('{{lookerField}}', prop_name.lower()) \
            .replace('{{tableField}}', prop_name.upper()) \
            .replace('{{type}}', 'string' if isinstance(prop, str) else 'number')

    '''
    Creates the main view for the table
    '''
    def create_view(self):
        table = self.config.get('table')
        if not table:
            raise ConverterException('No table prop! Aborting...')

        processed_props = '\n'.join([self.output[prop] for prop in self.output])
        processed_view = self.view_template \
            .replace('{{properties}}', processed_props) \
            .replace('{{lookerView}}', 'site_{}'.format(table.lower())) \
            .replace('{{tableName}}', table.upper())

        self.view = processed_view

    def save_files(self):
        if not hasattr(self, 'view'):
            raise ConverterException('No view has been created.')

        table_view = self.config.get('table').lower()

        view_file = 'site_{}.{}'.format(table_view, self.config['outputFileExtension'])

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

    def process(self):
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
        self.create_view()

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
