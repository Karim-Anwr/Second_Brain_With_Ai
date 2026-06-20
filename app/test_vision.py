from app.services.vision_service import VisionService

def main():
    # حط هنا الصورة اللي عايز تختبرها
    image_path = "Screenshot_2023-07-22-18-19-33-67_234a8a5469dba44abf15ea6fc15b7751.jpg"

    vision = VisionService()

    result = vision.analyze_image(image_path)

    print("\n" + "=" * 50)
    print("VISION RESULT")
    print("=" * 50)

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()