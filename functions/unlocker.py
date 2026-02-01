import pikepdf
import os


def unlock_pdf(file_name, password, input_folder="input", output_folder="output"):
    """
    Removes password from a PDF and saves it to the output folder.
    Returns the path of the unlocked file or None if failed.
    """

    input_path = os.path.join(input_folder, file_name)
    output_path = os.path.join(output_folder, f"unlocked_{file_name}")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print(f"🔓 Attempting to unlock: {input_path}...")

    try:
        with pikepdf.open(input_path, password=password) as pdf:
            pdf.save(output_path)

        print(f"✅ Success! File saved at: {output_path}")
        return output_path

    except pikepdf.PasswordError:
        print("❌ Error: Incorrect password.")
        return None
    except FileNotFoundError:
        print(f"❌ Error: File '{file_name}' not found in '{input_folder}'.")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


if __name__ == "__main__":
    # Test block
    unlock_pdf("test_file.pdf", "12345")
