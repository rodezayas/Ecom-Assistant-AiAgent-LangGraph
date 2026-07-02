1. Catálogo de productos (JSON)
   Ya lo tenías planeado — 40-60 productos con variantes de talla/color/stock. Este es el core.
2. Políticas de la tienda (Markdown/texto)

Política de devoluciones y cambios (plazos, condiciones, excepciones)
Política de envíos (tiempos, costos, zonas de cobertura)
Métodos de pago aceptados
Garantías por categoría (ej. calzado tiene garantía distinta a accesorios)

Esto es clave porque en entrevista te van a preguntar "¿cómo maneja el agente preguntas que no son de producto?" — y aquí tienes la respuesta lista: el intent router detecta "pregunta de política" y el RAG busca en esta colección separada, no en el catálogo. 3. Guía de tallas (Markdown/tabla)
Conversión de tallas por categoría (playeras vs. pantalones vs. calzado), medidas en cm, recomendaciones tipo "si estás entre M y L, elige M para fit ajustado."
Bueno para probar que el RAG puede responder preguntas indirectas (usuario pregunta "¿qué talla me recomiendan si uso 27 en tenis Nike?" sin mencionar el producto directamente). 4. FAQs de la marca (Markdown)
Preguntas frecuentes tipo "¿tienen tienda física?", "¿puedo cambiar de talla después de comprar?", "¿hacen envíos internacionales?" — esto te da casos de prueba fáciles para el dataset de evaluation. 5. Historial de pedidos simulado (JSON, opcional pero fuerte)
Un set falso de pedidos con order_id, chat_id, estado (procesando/enviado/entregado), fecha. Esto te permite meter un nodo extra al grafo: "consulta de status de pedido" que NO usa RAG semántico sino lookup determinístico — otra vez, separando bien "búsqueda semántica" de "consulta exacta a base de datos." Es exactamente el tipo de matiz que un entrevistador senior valora. 6. Reseñas de producto (texto corto, opcional)
2-3 reseñas falsas por producto ("me quedó perfecto," "la talla corre chica"). Le da al agente algo más que decir además de specs — y prueba que el RAG puede combinar múltiples chunks del mismo producto sin confundir fuentes.
Con esto tienes al menos 3 colecciones distintas en el vector store (catálogo, políticas, FAQs) más una fuente determinística (pedidos) — que es justo la complejidad que separa un proyecto de portfolio genérico de uno que demuestra pensamiento de production RAG.
