#!/bin/bash

# ============================================
# SCRIPT DE BUILD PARA CLIENTE TEMER ANDROID
# ============================================
# Autor: VempirE_GhosT
# Descrição: Automatiza build do APK Android
# ============================================

set -e  # Para o script em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções de log
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ========== CONFIGURAÇÃO ==========
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="Cliente Temer Android"
VENV_DIR="$PROJECT_DIR/venv"
BUILDOZER_SPEC="$PROJECT_DIR/buildozer.spec"
APK_OUTPUT_DIR="$PROJECT_DIR/bin"

log_info "Iniciando build do: $PROJECT_NAME"
log_info "Diretório do projeto: $PROJECT_DIR"

# ========== PASSO 1: VERIFICAR SE ESTÁ NO DIRETÓRIO CORRETO ==========
log_info "Verificando estrutura do projeto..."

if [ ! -f "$BUILDOZER_SPEC" ]; then
    log_warning "Arquivo buildozer.spec não encontrado!"
    log_info "Criando buildozer.spec padrão..."
    
    cat > "$BUILDOZER_SPEC" << 'EOF'
[app]
title = Cliente Temer Android
package.name = cliente_temer
package.domain = com.vempireghost
source.dir = .
source.main = main.py
version = 1.0
requirements = python3, kivy, plyer
android.permissions = INTERNET
android.api = 31
android.minapi = 21
android.sdk = 31
android.ndk = 23b
android.gradle_dependencies = 
android.allow_backup = True
android.fullscreen = 1
android.dpi = 160
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0

[buildozer]
log_level = 2
warn_on_root = 1
EOF
    
    log_success "buildozer.spec criado com configurações padrão"
fi

# ========== PASSO 2: CRIAR/ATIVAR AMBIENTE VIRTUAL ==========
log_info "Configurando ambiente virtual Python..."

if [ ! -d "$VENV_DIR" ]; then
    log_info "Criando ambiente virtual em: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        log_error "Falha ao criar ambiente virtual"
        log_info "Tentando com virtualenv..."
        pip3 install virtualenv
        virtualenv "$VENV_DIR"
    fi
    
    log_success "Ambiente virtual criado"
else
    log_info "Ambiente virtual já existe"
fi

# Ativar ambiente virtual
log_info "Ativando ambiente virtual..."
source "$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    log_error "Falha ao ativar ambiente virtual"
    exit 1
fi

log_success "Ambiente virtual ativado: $(which python)"

# ========== PASSO 3: INSTALAR DEPENDÊNCIAS ==========
log_info "Instalando dependências do Python..."

# Atualizar pip
python -m pip install --upgrade pip

# Instalar dependências básicas
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    log_info "Criando requirements.txt padrão..."
    cat > "$REQUIREMENTS_FILE" << 'EOF'
kivy==2.3.0
plyer==2.1.0
Cython==0.29.33
EOF
fi

pip install -r "$REQUIREMENTS_FILE"

# Instalar buildozer se não existir
if ! command -v buildozer &> /dev/null; then
    log_info "Instalando Buildozer..."
    pip install buildozer
else
    log_info "Buildozer já está instalado"
fi

# ========== PASSO 4: INSTALAR DEPENDÊNCIAS DO SISTEMA ==========
log_info "Verificando dependências do sistema..."

# Lista de dependências necessárias para Debian/Ubuntu
DEPS=(
    "git" "zip" "unzip" "openjdk-17-jdk"
    "python3-pip" "autoconf" "libtool" "pkg-config"
    "zlib1g-dev" "libncurses5-dev" "libncursesw5-dev"
    "libtinfo5" "cmake" "libffi-dev" "libssl-dev"
)

MISSING_DEPS=()
for dep in "${DEPS[@]}"; do
    if ! dpkg -l | grep -q "^\ii.*$dep"; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    log_warning "Instalando dependências do sistema: ${MISSING_DEPS[*]}"
    sudo apt-get update
    sudo apt-get install -y "${MISSING_DEPS[@]}"
    log_success "Dependências do sistema instaladas"
else
    log_info "Todas dependências do sistema já estão instaladas"
fi

# ========== PASSO 5: VERIFICAR ARQUIVO MAIN.PY ==========
log_info "Verificando arquivo principal..."

MAIN_PY="$PROJECT_DIR/main.py"
CLIENT_PY="$PROJECT_DIR/cliente_temer_android.py"

if [ ! -f "$MAIN_PY" ] && [ -f "$CLIENT_PY" ]; then
    log_warning "main.py não encontrado, mas cliente_temer_android.py existe"
    log_info "Criando link simbólico..."
    ln -sf "$CLIENT_PY" "$MAIN_PY"
    log_success "Link criado: main.py -> cliente_temer_android.py"
elif [ ! -f "$MAIN_PY" ]; then
    log_error "Nenhum arquivo principal encontrado!"
    log_info "Esperado: main.py ou cliente_temer_android.py"
    exit 1
fi

log_success "Arquivo principal verificado: $(basename "$MAIN_PY")"

# ========== PASSO 6: EXECUTAR BUILD ==========
log_info "Iniciando compilação do APK..."
log_info "Isso pode levar vários minutos na primeira vez..."

echo ""
log_warning "============================================="
log_warning "  INICIANDO BUILD - PODE LEVAR 30+ MINUTOS  "
log_warning "============================================="
echo ""

# Perguntar tipo de build
echo "Selecione o tipo de build:"
echo "  1) Debug padrão (recomendado para testes)"
echo "  2) Debug otimizado (mais rápido, menor)"
echo "  3) Cancelar"
echo -n "Escolha [1-3]: "
read -r build_choice

case $build_choice in
    1)
        BUILD_CMD="buildozer -v android debug"
        BUILD_TYPE="debug"
        ;;
    2)
        BUILD_CMD="buildozer android debug -- --mode=release"
        BUILD_TYPE="debug-opt"
        ;;
    3)
        log_info "Build cancelado pelo usuário"
        exit 0
        ;;
    *)
        log_warning "Escolha inválida, usando debug padrão"
        BUILD_CMD="buildozer -v android debug"
        BUILD_TYPE="debug"
        ;;
esac

log_info "Executando: $BUILD_CMD"
log_info "Tipo: $BUILD_TYPE"

# Executar build
if eval "$BUILD_CMD"; then
    log_success "✅ BUILD COMPLETADO COM SUCESSO!"
    
    # Encontrar APK gerado
    APK_FILE=$(find "$APK_OUTPUT_DIR" -name "*.apk" -type f | head -1)
    
    if [ -n "$APK_FILE" ]; then
        APK_SIZE=$(du -h "$APK_FILE" | cut -f1)
        log_success "APK gerado: $(basename "$APK_FILE")"
        log_success "Tamanho: $APK_SIZE"
        log_success "Local: $APK_FILE"
        
        echo ""
        log_warning "📱 PRÓXIMOS PASSOS:"
        log_info "1. Transfira o APK para seu celular"
        log_info "2. Ative 'Fontes desconhecidas' nas configurações"
        log_info "3. Instale usando gerenciador de arquivos"
        log_info "4. Conceda permissão de INTERNET ao app"
        
        # Tentar abrir a pasta no gerenciador de arquivos
        if command -v xdg-open &> /dev/null; then
            echo ""
            log_info "Abrindo pasta com o APK..."
            xdg-open "$APK_OUTPUT_DIR"
        fi
    else
        log_warning "APK não encontrado na pasta bin/"
    fi
else
    log_error "❌ BUILD FALHOU!"
    log_info "Verifique os logs acima para detalhes do erro"
    exit 1
fi

# ========== FIM ==========
echo ""
log_success "Script concluído em: $(date)"
log_info "Ambiente virtual ainda ativo. Para desativar: deactivate"
