from django.contrib import admin

from .models import Currency, ProductType, TourismProduct

admin.site.register(Currency)
admin.site.register(ProductType)
admin.site.register(TourismProduct)
