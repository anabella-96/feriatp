# =============================================================================
#  back/camera_module/__init__.py
#
#  Módulo de la CÁMARA y RECONOCIMIENTO FACIAL.
#
#  CONTENIDO:
#    - routes.py                     -> endpoints HTTP (registrar_rostro, reconocer)
#    - services/face_service.py      -> lógica de reconocimiento facial (DeepFace)
#    - services/db_service.py        -> acceso a la base de datos MySQL
#
#  El Blueprint `camera_bp` (routes.py) se registra en back/app.py.
# =============================================================================