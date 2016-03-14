# -*- coding: utf-8 -*-
"""
    import_catalog

    Import catalog

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: AGPLv3, see LICENSE for more details.
"""
from magento.catalog import Category, Product
from openerp.osv import osv
from openerp.tools.translate import _


class ImportCatalog(osv.TransientModel):
    "Import catalog"
    _name = 'magento.instance.import_catalog'

    def import_catalog(self, cursor, user, ids, context):
        """
        Import the product categories and products

        :param cursor: Database cursor
        :param user: ID of current user
        :param ids: List of ids of records for this model
        :param context: Application context
        """
        Pool = self.pool
        website_obj = Pool.get('magento.instance.website')

        website = website_obj.browse(
            cursor, user, context['active_id'], context
        )

        self.import_category_tree(cursor, user, website, context)
        product_ids = self.import_products(cursor, user, website, context)

        return self.open_products(
            cursor, user, ids, product_ids, context
        )

    def import_category_tree(self, cursor, user, website, context):
        """
        Imports category tree

        :param cursor: Database cursor
        :param user: ID of current user
        :param website: Browse record of website
        :param context: Application context
        """
        category_obj = self.pool.get('product.category')

        instance = website.instance
        context.update({
            'magento_instance': instance.id
        })

        with Category(
            instance.url, instance.api_user, instance.api_key
        ) as category_api:
            category_tree = category_api.tree(website.magento_root_category_id)

            category_obj.create_tree_using_magento_data(
                cursor, user, category_tree, context
            )

    def import_products(self, cursor, user, website, context):
        """
        Imports products for current instance

        :param cursor: Database cursor
        :param user: ID of current user
        :param website: Browse record of website
        :param context: Application context
        :return: List of product IDs
        """
        product_obj = self.pool.get('product.product')

        instance = website.instance
        import csv
        def dict2row(PCMRP,rec):
            out=[]
            for p in PCMRP:
                out.append(rec[p])
            return out
    
        def save_csv(fn, data, HEADER=None):
            if len(data)>0:
                if HEADER is None:
                    HEADER=data[0].keys()
            fp = open(fn, 'wb')
            out=[dict2row(HEADER, x) for x in data]
            csv_writer=csv.writer(fp)
            csv_writer.writerows( [HEADER]+out )
            fp.close()
        with Product(
            instance.url, instance.api_user, instance.api_key
        ) as product_api:
            mag_products = []
            products = []

            # Products are linked to websites. But the magento api filters
            # the products based on store views. The products available on
            # website are always available on all of its store views.
            # So we get one store view for each website in current instance.
            mag_products.extend(
                product_api.list(
                    store_view=website.stores[0].store_views[0].magento_id
                )
            )
            context.update({
                'magento_website': website.id
            })
            mg_skus=[]
            import pprint
            
            #import galtyslib.openerplib as openerplib
            mg_map = dict([ (x['sku'],x) for x in mag_products])
            mg_skus = [x['sku'] for x in mag_products]
            prod_obj=self.pool.get('product.product')
            prod_ids=prod_obj.search(cursor, user, [])
            prods = [x for  x in prod_obj.browse(cursor, user, prod_ids) ]
            erp_products=[ dict(erp_sku=x.default_code,erp_name=x.name.encode('utf8') ) for x in prods]
            erp_map = dict([ (x['erp_sku'],x) for x in erp_products])
            erp_skus=[x['erp_sku'] for x in erp_products]
            
            out=[]
            for sku in set(mg_skus).union(set(erp_skus)) - set(mg_skus).intersection( set(erp_skus) ):
                mg=mg_map.get(sku)
                erp=erp_map.get(sku)
                rec={}
                if mg:
                    x=dict(sku=mg['sku'],name=mg['name'].encode('utf8'))
                    rec.update(x)
                else:
                    x=dict(sku='',name='')
                    rec.update(x)
                if erp:
                    rec.update(erp)
                else:
                    x=dict(erp_sku='',erp_name='')
                    rec.update(x)

                out.append(rec)
                
            #print out
            save_csv('mg_erp_skus_cmp_pjb_live.csv', out)
            import xmlrpclib
            for mag_product in mag_products:
                #pprint.pprint(mag_product)
                try:
                    products.append(product_obj.find_or_create_using_magento_id(cursor, user, mag_product['product_id'], context) )
                except xmlrpclib.ProtocolError:
                    print 'ERROR',mag_product
                    continue
            #print products
        return map(int, products)

    def open_products(self, cursor, user, ids, product_ids, context):
        """
        Opens view for products for current instance

        :param cursor: Database cursor
        :param user: ID of current user
        :param ids: List of ids of records for this model
        :param product_ids: List or product IDs
        :param context: Application context
        :return: View for products
        """
        ir_model_data = self.pool.get('ir.model.data')

        tree_res = ir_model_data.get_object_reference(
            cursor, user, 'product', 'product_product_tree_view'
        )
        tree_id = tree_res and tree_res[1] or False

        return {
            'name': _('Magento Instance Products'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'product.product',
            'views': [(tree_id, 'tree')],
            'context': context,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', product_ids)]
        }

ImportCatalog()
