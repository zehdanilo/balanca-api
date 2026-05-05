import socket
from dataclasses import dataclass
from typing import Optional, Iterator

STX = 0x02
CR  = 0x0D

@dataclass
class P03Frame:
    swa: int
    swb: int
    swc: int
    peso_raw: str   # 6 ASCII
    tara_raw: str   # 6 ASCII
    peso: int       # convertido
    tara: int
    checksum: Optional[int] = None

def twos_complement_checksum(payload: bytes) -> int:
    """
    Checksum P03 (quando habilitado):
    complemento de 2 da soma dos bytes de STX até CR (inclusive).
    Ou seja: CS = (-sum(payload)) & 0xFF
    """
    s = sum(payload) & 0xFF
    return ((-s) & 0xFF)

def parse_p03_frame(frame: bytes) -> P03Frame:
    """
    frame inclui: STX ... CR [CS]
    Layout:
      [0]=STX
      [1]=SWA [2]=SWB [3]=SWC
      [4:10]=PPPPPP (6 ASCII)
      [10:16]=TTTTTT (6 ASCII)
      [16]=CR
      [17]=CS (opcional)
    """
    if len(frame) not in (17, 18):
        raise ValueError(f"Tamanho inválido: {len(frame)} bytes (esperado 17 ou 18)")

    if frame[0] != STX or frame[16] != CR:
        raise ValueError("Frame sem STX/CR nos locais esperados")

    swa, swb, swc = frame[1], frame[2], frame[3]
    peso_raw = frame[4:10].decode("ascii", errors="strict")
    tara_raw = frame[10:16].decode("ascii", errors="strict")

    peso = int(peso_raw.strip() or "0")
    tara = int(tara_raw.strip() or "0")

    cs = None
    if len(frame) == 18:
        cs = frame[17]
        calc = twos_complement_checksum(frame[:17])  # STX..CR
        if cs != calc:
            raise ValueError(f"Checksum inválido: recebido={cs:02X}, calculado={calc:02X}")

    return P03Frame(swa=swa, swb=swb, swc=swc,
                    peso_raw=peso_raw, tara_raw=tara_raw,
                    peso=peso, tara=tara, checksum=cs)

def iter_p03_frames(sock: socket.socket) -> Iterator[bytes]:
    """
    Extrai frames do stream TCP.
    Estratégia:
      - sincroniza em STX
      - lê tamanho fixo (17) e decide se há CS (18) olhando um byte extra opcional
    """
    buf = bytearray()

    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Conexão encerrada pelo equipamento")
        buf.extend(chunk)

        while True:
            try:
                i = buf.index(STX)
            except ValueError:
                buf.clear()
                break

            if i > 0:
                del buf[:i]

            if len(buf) < 17:
                break

            candidate17 = bytes(buf[:17])
            if candidate17[16] != CR:
                del buf[0]
                continue

            if len(buf) >= 18:
                candidate18 = bytes(buf[:18])
                yield candidate18
                del buf[:18]
            else:
                yield candidate17
                del buf[:17]
