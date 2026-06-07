from django.contrib import admin
from .models import Vehicle, Driver, Route, FuelLog, Maintenance, Telemetry

admin.site.register(Vehicle)
admin.site.register(Driver)
admin.site.register(Route)
admin.site.register(FuelLog)
admin.site.register(Maintenance)
admin.site.register(Telemetry)
