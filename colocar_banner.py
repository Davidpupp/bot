#!/usr/bin/env python3
"""
Script para ajudar a colocar o banner no bot
"""

import os
import shutil

def colocar_banner():
    print("=== Colocar Banner no Bot ===")
    print()
    print("Para colocar seu banner:")
    print("1. Salve sua imagem como 'welcome_banner.jpg'")
    print("2. Mova para a pasta 'banners/'")
    print()
    
    # Verificar se a pasta existe
    if not os.path.exists("banners"):
        print("Criando pasta 'banners'...")
        os.makedirs("banners")
    
    # Verificar se já existe um banner
    banner_path = "banners/welcome_banner.jpg"
    if os.path.exists(banner_path):
        print("Banner já encontrado em:", banner_path)
        print("Tamanho:", os.path.getsize(banner_path), "bytes")
    else:
        print("Banner não encontrado ainda.")
        print("Por favor, coloque sua imagem em:", banner_path)
    
    print()
    print("Quando terminar, execute /start no bot para testar!")

if __name__ == "__main__":
    colocar_banner()
