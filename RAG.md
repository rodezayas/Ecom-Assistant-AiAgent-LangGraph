1. Formato por tipo de documento

Catálogo de productos → JSON (no markdown). Es data estructurada; cada producto es un chunk natural. No necesitas chunking manual, el documento completo por producto ya es la unidad ideal.
Políticas, FAQs, guía de tallas → Markdown con headers claros (##). Cada sección bajo un header se vuelve un chunk lógico — esto te da control natural del chunking sin necesitar un splitter complejo.
Reseñas → JSON, agrupadas por product_id, cada reseña como string corto dentro de una lista.

2. Metadata es lo que hace la diferencia
   Cada chunk que metas al vector store debería llevar metadata explícita, no solo el texto:
   json{
   "content": "...",
   "metadata": {
   "source_type": "policy" | "product" | "faq" | "size_guide" | "review",
   "category": "shipping" | "returns" | "payments",
   "product_id": "opcional, si aplica"
   }
   }
   Esto te permite filtrar el retrieval por tipo de fuente antes de hacer la búsqueda semántica (ej. si el intent router detecta "pregunta de política," filtras a source_type: policy y no compites contra el catálogo completo). En entrevista, esto demuestra que entiendes retrieval más allá de "meter todo a un solo índice."
3. Tamaño de chunk

Políticas/FAQs: 150-300 tokens por chunk, un concepto por chunk (no mezclar política de envío con política de devolución en el mismo chunk).
Productos: no fragmentes — un producto completo (nombre + descripción + tags) es una unidad, porque fragmentarlo rompe el contexto que necesita el LLM para responder bien.

4. Genera con LLM, pero con estructura fija
   Te recomiendo generar cada colección con un prompt que fuerce el schema exacto (Pydantic incluso para la generación), así el output ya viene limpio y consistente en vez de tener que normalizarlo después.
5. Casos "trampa" a propósito
   Mete a propósito algunos productos sin stock, alguna política con excepción rara, y una pregunta de FAQ ambigua. Esto es oro para tu dataset de evaluation después — pruebas si el agente alucina cuando la respuesta real es "no tengo esa información."
