"""Cola local de eventos pendientes de sync.

Persistida en SQLite (tabla aparte) para no perder eventos si la Pi se
reinicia sin red. Drena en orden cuando vuelve la conectividad.
"""
