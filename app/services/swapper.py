import insightface
from insightface.app import FaceAnalysis
import concurrent.futures
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class FaceSwapper:
    def __init__(self, analyzer=None, swapper=None):
        """
        Initialize FaceSwapper with pre-loaded models.
        If models are not provided, they will be loaded (for backward compatibility).
        
        :param analyzer: Pre-loaded FaceAnalysis analyzer model
        :param swapper: Pre-loaded face swapper model
        """
        if analyzer is not None and swapper is not None:
            # Use pre-loaded models
            self.analyzer = analyzer
            self.swapper = swapper
            logger.info("FaceSwapper initialized with pre-loaded models")
        else:
            # Load models (for backward compatibility)
            logger.warning("Loading models in __init__ - consider using lifespan for better performance")
            self.analyzer_model_name = 'buffalo_l'
            self.analyzer = FaceAnalysis(name=self.analyzer_model_name)
            self.analyzer.prepare(ctx_id=0, det_size=(640, 640))
            self.swapper_model_path = settings.model_artifact_path
            self.swapper = insightface.model_zoo.get_model(self.swapper_model_path, download=False, providers=["CoreMLExecutionProvider"])
    
    @staticmethod
    def load_models():
        """
        Load and return the face analysis and swapper models.
        This should be called during application startup.
        
        :return: Tuple of (analyzer, swapper) models
        """
        logger.info("Loading face analysis model (buffalo_l)...")
        analyzer_model_name = 'buffalo_l'
        analyzer = FaceAnalysis(name=analyzer_model_name)
        analyzer.prepare(ctx_id=0, det_size=(640, 640))
        logger.info("Face analysis model loaded successfully")
        
        logger.info(f"Loading face swapper model from {settings.model_artifact_path}...")
        swapper_model_path = settings.model_artifact_path
        swapper = insightface.model_zoo.get_model(swapper_model_path, download=False, providers=["CoreMLExecutionProvider"])
        logger.info("Face swapper model loaded successfully")
        
        return analyzer, swapper

    def get_face_embedding(self, source_img):
        """
        Get face embedding from the source image.
        :param source_img: Image (numpy array) containing the source face
        :return: Face embedding object or None if no face detected
        """
        faces = self.analyzer.get(source_img)
        if not faces:
            return None
        return faces[0]

    def swap_faces(self, frame, source_face):
        """
        Swap faces in a single frame using the provided source face embedding.
        :param frame: Target frame (numpy array)
        :param source_face: Face embedding object from source image
        :return: Frame with swapped face or original frame if no face detected
        """
        res = frame.copy()
        faces = self.analyzer.get(frame)
        if not faces or source_face is None:
            # No faces detected or no source face embedding, return original frame
            return frame
        dest_image = faces[0]
        res = self.swapper.get(res, dest_image, source_face, paste_back=True)
        return res

    def swap_faces_concurrent(self, frames, source_faces, max_workers=4):
        """
        Process multiple frames concurrently using threading.
        :param frames: List of frames to process
        :param source_faces: List of source face embeddings corresponding to each frame
        :param max_workers: Number of threads to use
        :return: List of processed frames
        """
        if len(frames) != len(source_faces):
            raise ValueError("frames and source_faces must have the same length")

        def process_pair(args):
            frame, source_face = args
            return self.swap_faces(frame, source_face)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_pair, zip(frames, source_faces)))
        return results
