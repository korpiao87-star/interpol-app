from PIL import Image

def make_image_pale(input_path, output_path, fade_level=0.5):
    """
    이미지를 하얀색과 합성하여 색을 옅게 만듭니다.
    
    :param input_path: 원본 이미지 경로
    :param output_path: 저장할 이미지 경로
    :param fade_level: 옅게 만드는 정도 (0.0: 완전 하얗게 ~ 1.0: 원본 그대로)
                      예를 들어 0.5는 원본 50%, 하얀색 50%를 섞습니다.
    """
    try:
        # 1. 원본 이미지 열기
        img = Image.open(input_path)
        
        # 2. 이미지가 RGBA(투명도 채널 포함)가 아니라면 변환 (PNG 등 권장)
        # 만약 JPG라면 RGB로 변환하여 처리할 수도 있습니다.
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 3. 같은 크기의 하얀색 배경 이미지 생성
        # 'RGBA' 모드이므로 (R, G, B, A) 형식입니다. (255, 255, 255, 255)는 완전 하얀색.
        white_bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        
        # 4. 두 이미지를 fade_level 비율로 합성 (블렌딩)
        # Image.blend(im1, im2, alpha) 함수는 (im1 * (1 - alpha) + im2 * alpha) 공식을 사용합니다.
        # 여기서 우리가 원하는 결과(옅게)를 얻기 위해 원본(img)과 하얀색(white_bg)을 블렌딩합니다.
        
        # 매개변수 이름을 'fade_level'로 했지만 Image.blend의 alpha 값과 혼동될 수 있으니
        # Image.blend(원본, 하얀색, fade_level) -> (원본 * (1-fade_level) + 하얀색 * fade_level)
        # 즉, fade_level이 클수록 하얀색이 강해져서 더 옅어집니다.
        # 따라서 사용자에게는 1 - fade_level을 적용하여 0.0이 완전 하얗게, 1.0이 원본이 되도록 합니다.
        
        # Image.blend(im1, im2, alpha) -> im1 * (1-alpha) + im2 * alpha
        # 우리가 원하는 결과 = 원본 * fade_level + 하얀색 * (1 - fade_level)
        # 이 식을 얻기 위해 함수 매개변수를 다음과 같이 설정합니다.
        
        result_img = Image.blend(white_bg, img, fade_level)
        
        # 5. 결과 저장 (JPG로 저장하려면 RGB로 변환해야 함)
        if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
            result_img = result_img.convert('RGB')
        
        result_img.save(output_path)
        print(f"이미지 색을 {fade_level:.1f} 수준으로 옅게 만들어 '{output_path}'에 저장했습니다.")

    except FileNotFoundError:
        print(f"오류: '{input_path}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"알 수 없는 오류 발생: {e}")

# --- 실행 예시 ---
# 원본 파일명
input_filename = 'blue_tiger.png'
# 저장할 파일명
output_filename = 'blue_tiger_pale.png'

# 이미지 색을 0.3 수준으로 옅게 만듭니다 (0.0: 하얗게 ~ 1.0: 원본)
# 즉, 원본 30%, 하얀색 70% 비율로 합성됩니다.
make_image_pale(input_filename, output_filename, fade_level=0.3)
