from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# CORE ALGORITHM
# docs are stored as reference to content
documents = {
    "AI.txt": """
    Artificial intelligence is the field of building machines
    that can perform tasks that normally require human intelligence.
    Machine learning is a part of artificial intelligence.
    Deep learning is a type of machine learning that uses neural networks.
    """,

    "RAG.txt": """
    Retrieval augmented generation, or RAG, combines information
    retrieval with text generation. A document is divided into chunks.
    Each chunk is converted into a vector and stored in a vector store.
    When a question is asked, the most relevant chunks are retrieved.
    These chunks are then provided to the language model as context.
    """,

    "Python.txt": """
    Python is a high level programming language.
    It is widely used in artificial intelligence, machine learning,
    data science and web development.
    Python has a simple and readable syntax.
    """
}

def create_chunks(documents, chunk_size=2, overlap=1):

    chunks = []

    for source, text in documents.items():

        # split document into sentences
        sentences = [
            s.strip()
            for s in text.split(".")
            if s.strip()
        ]

        # create overlapping chunks
        start = 0

        while start < len(sentences):

            end = min(start + chunk_size, len(sentences))

            chunk_text = ". ".join(sentences[start:end]) + "."

            chunks.append({
                "text": chunk_text,
                "source": source,
                "position": start
            })

            # move forward while keeping overlap
            start += chunk_size - overlap

    return chunks

def build_index(chunks):

    # Take only the text from each chunk
    texts = [chunk["text"] for chunk in chunks]

    # TF-IDF converts every chunk into a vector
    vectorizer = TfidfVectorizer(stop_words="english")

    matrix = vectorizer.fit_transform(texts)

    return vectorizer, matrix

def retrieve(query, vectorizer, matrix, chunks, k=2):

    # Convert the query into a TF-IDF vector
    query_vector = vectorizer.transform([query])

    # Calculate cosine similarity between query and every chunk
    scores = cosine_similarity(query_vector, matrix)[0]

    # Sort chunks by similarity score
    ranked = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True
    )

    # Take top-k chunks
    results = []

    for i in ranked[:k]:

        results.append({
            "text": chunks[i]["text"],
            "source": chunks[i]["source"],
            "position": chunks[i]["position"],
            "score": scores[i]
        })

    return results

def build_context(results):

    context = ""

    for r in results:

        context += (
            f"[Source: {r['source']}, "
            f"Chunk: {r['position']}]\n"
        )

        context += r["text"] + "\n\n"

    return context


# we simply show the retrieved context as the grounded evidence
def grounded_answer(query, results):

    context = build_context(results)

    return (
        "Answer based on the retrieved context:\n"
        + context
        + "Citation: "
        + ", ".join(r["source"] for r in results)
    )

def baseline_answer(query):

    return (
        "Ungrounded answer for: "
        + query
        + "\n(No retrieved evidence was provided.)"
    )

print("Core Rag")
print()

chunks = create_chunks(
    documents,
    chunk_size=2,
    overlap=1
)

print("\nNumber of chunks indexed:", len(chunks))

vectorizer, matrix = build_index(chunks)

questions = [
    "What is retrieval augmented generation?",
    "What is Python used for?"
]

for question in questions:

    print("QUESTION:", question)
    print()

    # retrieve top 2 chunks
    results = retrieve(
        question,
        vectorizer,
        matrix,
        chunks,
        k=2
    )

    print("\nRETRIEVED CHUNKS:")

    for r in results:

        print(
            f"Score: {r['score']:.4f} | "
            f"Source: {r['source']} | "
            f"Chunk: {r['position']}"
        )

        print("Text:", r["text"])

    # Grounded answer
    print("\nGROUNDED ANSWER:")
    print(grounded_answer(question, results))

    # Ungrounded answer
    print("\nUNGROUNDED BASELINE:")
    print(baseline_answer(question))


# ex 1: Similarity Threshold
print("\nEXERCISE 1 - SIMILARITY THRESHOLD")
def answer_with_threshold(
    query,
    vectorizer,
    matrix,
    chunks,
    k=2,
    threshold=0.20
):

    results = retrieve(
        query,
        vectorizer,
        matrix,
        chunks,
        k
    )

    # Best retrieved chunk has the highest score
    best_score = results[0]["score"]

    print("\nQuestion:", query)

    print("Best similarity:", round(best_score, 4))

    # If even the best chunk is below threshold,
    # we do not trust the retrieval.
    if best_score < threshold:

        print("Answer: The answer is not in the corpus.")
        return

    # Otherwise use the retrieved context
    print("\nRetrieved evidence:")

    for r in results:

        print(
            f"[{r['source']}, score={r['score']:.4f}] "
            f"{r['text']}"
        )

    print("\nAnswer:")
    print("The answer is supported by the retrieved context.")


# Two questions the corpus CAN answer
answerable_questions = [
    "What is Python used for?",
    "What is retrieval augmented generation?"
]

# Two questions the corpus CANNOT answer
unanswerable_questions = [
    "Who invented the telephone?",
    "What is the capital of Japan?"
]


print("\n--- Answerable Questions ---")

for question in answerable_questions:

    answer_with_threshold(
        question,
        vectorizer,
        matrix,
        chunks,
        k=2,
        threshold=0.20
    )


print("\n--- Unanswerable Questions ---")

for question in unanswerable_questions:

    answer_with_threshold(
        question,
        vectorizer,
        matrix,
        chunks,
        k=2,
        threshold=0.20
    )


# ============================================================
# EXERCISE 2
# Compare Chunk Size and Overlap
# ============================================================

print("\nEXERCISE 2 - CHUNK SIZE / OVERLAP")


# At least four different settings as required
settings = [
    (1, 0),
    (2, 0),
    (2, 1),
    (3, 1)
]


# Questions with known answers in the corpus
test_questions = [
    "What is retrieval augmented generation?",
    "What is Python used for?"
]


for chunk_size, overlap in settings:

    print("\n" + "-" * 60)

    print(
        f"Chunk size = {chunk_size}, "
        f"Overlap = {overlap}"
    )

    # Build chunks using this configuration
    test_chunks = create_chunks(
        documents,
        chunk_size,
        overlap
    )

    # Build a new TF-IDF index
    test_vectorizer, test_matrix = build_index(
        test_chunks
    )

    print(
        "Number of chunks:",
        len(test_chunks)
    )

    for question in test_questions:

        results = retrieve(
            question,
            test_vectorizer,
            test_matrix,
            test_chunks,
            k=len(test_chunks)
        )

        # Find the chunk that actually contains
        # the answer by checking the source text.
        #
        # For this experiment:
        # RAG question -> RAG.txt
        # Python question -> Python.txt

        if "retrieval" in question.lower():

            expected_source = "RAG.txt"

        else:

            expected_source = "Python.txt"

        answer_chunk = None

        for r in results:

            if r["source"] == expected_source:

                answer_chunk = r
                break

        # Find rank of the answer-containing chunk
        rank = None

        for i, r in enumerate(results):

            if r["source"] == expected_source:

                rank = i + 1
                break

        print("\nQuestion:", question)

        if answer_chunk:

            print(
                "Answer chunk rank:",
                rank
            )

            print(
                "Similarity score:",
                round(answer_chunk["score"], 4)
            )

            print(
                "Source:",
                answer_chunk["source"]
            )

            print(
                "Chunk:",
                answer_chunk["text"]
            )

        else:

            print(
                "Answer-containing chunk was not found."
            )
