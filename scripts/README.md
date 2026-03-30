# Scripts de Tenant

## create_tenant.py

Cria a estrutura de pasta do tenant em `iagencia-core/tenant_context/<slug>` e imprime o SQL de UPSERT para o Supabase.

### Uso

```bash
python /Users/daniloportela/Desktop/TESTES_IA/meu_app/iagencia-core/scripts/create_tenant.py \
  --name "Carol Graber" \
  --slug carol-graber \
  --modules dashboard,atendimento,planning,creation,image_studio,library,approvals
```

### Opcional (legado)

Se você ainda usa `tenants_context/<slug>/brand_guide.md`:

```bash
python /Users/daniloportela/Desktop/TESTES_IA/meu_app/iagencia-core/scripts/create_tenant.py \
  --name "Carol Graber" \
  --slug carol-graber \
  --legacy-context
```

O script imprime o SQL necessário para inserir/atualizar o tenant no Supabase.
