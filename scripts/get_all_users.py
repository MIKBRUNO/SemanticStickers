from qdrant_client import QdrantClient

q = QdrantClient(
    url="{url}",
    api_key="{apikey}"
)
r = q.search_groups(
    collection_name="{collection}",
    query_vector=[0]*768,
    group_by="chat_id",
    group_size=1,
    limit=100000
)
groups = r.groups
for group in groups:
    print(group.hits[0].payload['chat_id'])
