# Spread

Live: https://pxd2.github.io/spread/

Lotus-style sheet for angelwood-67. Downloads an eBay Seller Hub CSV whose first line is locked:

    Info,Version=1.0.0,Template=fx_category_template_EBAY_US

eBay rejects any other first line with "We couldn’t identify your template."

Do not re-save the CSV in Excel. Excel prepends a BOM and the upload fails again.
