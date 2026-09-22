# =============================================================================
#  back/ssl_utils.py
#
#  Genera un certificado SSL autofirmado para el servidor.
#
#  ¿POR QUÉ ES NECESARIO?
#    El navegador solo permite usar la cámara (navigator.mediaDevices.
#    getUserMedia) en un "contexto seguro": https:// o localhost.
#    Si otro dispositivo de la red entra con http://IP:5000, la cámara NO
#    funciona (navigator.mediaDevices es undefined).
#    Al servir HTTPS (https://IP:5001), la cámara sí funciona desde cualquier
#    equipo de la red (el navegador pedirá confirmar el certificado autofirmado).
# =============================================================================

import datetime
import ipaddress
import os
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _ips_locales():
    """Recoge las IPs de las interfaces de red de este equipo."""
    ips = {"127.0.0.1"}
    try:
        nombre = socket.gethostname()
        for info in socket.getaddrinfo(nombre, None):
            ip = info[4][0]
            if ":" not in ip:  # Solo IPv4.
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def _ips_rango_lan():
    """
    Todas las IPs de la red local privada 192.168.1.1..192.168.1.254.

    El certificado debe incluir TODO este rango: así funciona la cámara
    sin importar qué IP tenga este equipo dentro de la red (cualquier
    número después de 192.168.1 define el dispositivo pero siempre es uno
    de esta subred). Si solo se incluyera la IP actual, al cambiar la IP
    del PC (DHCP) el certificado dejaría de servir y el navegador
    bloquearía la cámara.
    """
    return [f"192.168.1.{i}" for i in range(1, 255)]


def _sans_deseados():
    """SANs (localhost + IPs del equipo + todo el rango 192.168.1.x)."""
    nombres = [x509.DNSName("localhost")]
    for ip in _ips_locales() + _ips_rango_lan():
        try:
            nombres.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except Exception:
            continue
    return nombres


def _cert_cubre_las_ips(ruta_cert):
    """Comprueba si un certificado ya incluye el rango 192.168.1.x completo."""
    try:
        with open(ruta_cert, "rb") as f:
            certificado = x509.load_pem_x509_certificate(f.read())
        san = certificado.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        actuales = {str(v) for v in san.get_values_for_type(x509.IPAddress)}
        deseadas = set(_ips_rango_lan())
        return deseadas <= actuales
    except Exception:
        return False


def ensure_certificate(destino=None):
    """
    Devuelve (ruta_cert, ruta_clave). Si no existen, crea el certificado
    autofirmado en back/ssl/. Incluye localhost, las IPs del equipo y todo
    el rango 192.168.1.x para que la cámara sirva desde cualquier IP de la
    red local aunque el equipo cambie de dirección.
    """
    if destino is None:
        base = os.path.dirname(os.path.abspath(__file__))  # carpeta back/
        destino = os.path.join(base, "ssl")

    cert_path = os.path.join(destino, "cert.pem")
    key_path = os.path.join(destino, "key.pem")

    # Si ya existen y cubren el rango 192.168.1.x completo, no regenerar.
    if (
        os.path.exists(cert_path)
        and os.path.exists(key_path)
        and _cert_cubre_las_ips(cert_path)
    ):
        return cert_path, key_path

    os.makedirs(destino, exist_ok=True)

    # Clave privada RSA 2048.
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    sujeto = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Asistec Local"),
    ])

    # Incluir localhost, las IPs del equipo y todo el rango 192.168.1.x como
    # "nombres alternativos" para que el navegador pueda abrir el certificado
    # desde cualquier dispositivo de la red local.
    nombres_alt = _sans_deseados()

    ahora = datetime.datetime.now(datetime.timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(sujeto)
        .issuer_name(sujeto)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(days=1))
        .not_valid_after(ahora + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(nombres_alt), critical=False)
        .sign(clave, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(
            clave.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )

    with open(cert_path, "wb") as f:
        f.write(certificado.public_bytes(serialization.Encoding.PEM))

    return cert_path, key_path