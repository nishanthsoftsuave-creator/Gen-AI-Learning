from load_pdf import load_pdf


def _add_overlap(chunks, chunk_overlap):
    if chunk_overlap <= 0:
        return chunks

    overlapped_chunks = []

    for index, chunk in enumerate(chunks):
        if index == 0:
            overlapped_chunks.append(chunk)
            continue

        previous_tail = chunks[index - 1][-chunk_overlap:]
        overlapped_chunks.append(f"{previous_tail}{chunk}")

    return overlapped_chunks


def recursive_chunk_text(text, chunk_size=900, chunk_overlap=150):
    separators = ["\n\n", "\n", ". ", " ", ""]

    def split_recursively(value, available_separators):
        value = value.strip()

        if not value:
            return []

        if len(value) <= chunk_size:
            return [value]

        separator = available_separators[0]

        if separator == "":
            return [
                value[index:index + chunk_size].strip()
                for index in range(0, len(value), chunk_size)
                if value[index:index + chunk_size].strip()
            ]

        chunks = []
        current = ""

        for piece in value.split(separator):
            piece = piece.strip()

            if not piece:
                continue

            candidate = piece if not current else f"{current}{separator}{piece}"

            if len(candidate) <= chunk_size:
                current = candidate
                continue

            if current:
                chunks.append(current.strip())

            if len(piece) > chunk_size:
                chunks.extend(
                    split_recursively(piece, available_separators[1:])
                )
                current = ""
            else:
                current = piece

        if current:
            chunks.append(current.strip())

        return chunks

    chunks = split_recursively(text, separators)
    return _add_overlap(chunks, chunk_overlap)


def chunk_text(text):
    return recursive_chunk_text(text)


if __name__ == "__main__":
    text = load_pdf()

    chunks = chunk_text(text)

    print("\n========== CHUNKING RESULT ==========")
    print(f"Total text length: {len(text)}")
    print(f"Number of chunks: {len(chunks)}")

    for index, chunk in enumerate(chunks, start=1):
        print(f"\n========== CHUNK {index} ==========")
        print(chunk)
