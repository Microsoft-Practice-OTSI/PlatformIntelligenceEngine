#!/usr/bin/env python
"""Check what factories are in the repository"""
from pie.discovery.repository import get_repository

tenant_id = 'default-tenant'
repo = get_repository()
factories = repo.list_factories(tenant_id=tenant_id)

print(f'Factories in repo (tenant={tenant_id}): {len(factories)} found')
for f in factories:
    print(f'  - {f.factory_name} (subscription: {f.subscription_id}, pipelines: {len(f.pipelines)})')

factory = repo.get_factory('df-dataintegration-uat', tenant_id=tenant_id)
status = factory.factory_name if factory else 'NOT FOUND'
print(f'Direct lookup for df-dataintegration-uat: {status}')

# Also try without tenant ID
factory2 = repo.get_factory('df-dataintegration-uat')
status2 = factory2.factory_name if factory2 else 'NOT FOUND'
print(f'Lookup without tenant ID: {status2}')
