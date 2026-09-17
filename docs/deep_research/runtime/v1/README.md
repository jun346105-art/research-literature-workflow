# Durable Runtime Kernel v1 Schemas

`run_state.schema.json`, `run_event.schema.json`, and `checkpoint.schema.json` are deterministic Pydantic v2 exports for `dr-runtime-v1`. Tests regenerate them in a temporary directory and compare bytes. They describe an offline lifecycle kernel, not a LangGraph graph, provider protocol, budget policy, or production output format.
