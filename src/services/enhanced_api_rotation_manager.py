"""
Sistema Avançado de Rotação de APIs - V3.0
Garante alta disponibilidade com fallback automático entre múltiplas APIs
ATUALIZADO: Implementa fallbacks Jina->EXA, Qwen->Gemini, Supadata para insights sociais
"""

import os
import time
import random
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime, timedelta
import threading
import requests
import asyncio
import aiohttp
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

logger = logging.getLogger(__name__)

class APIStatus(Enum):
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    OFFLINE = "offline"

@dataclass
class APIEndpoint:
    name: str
    api_key: str
    base_url: str
    status: APIStatus = APIStatus.ACTIVE
    last_used: datetime = None
    error_count: int = 0
    rate_limit_reset: datetime = None
    requests_made: int = 0
    max_requests_per_minute: int = 60

class EnhancedAPIRotationManager:
    """
    Gerenciador avançado de rotação de APIs com:
    - Fallback automático entre modelos
    - Rate limiting inteligente
    - Health checking
    - Balanceamento de carga
    """
    
    def __init__(self):
        self.apis = {
            'qwen': [],
            'gemini': [],
            'groq': [],
            'openai': [],
            'deepseek': [],
            'jina': [],
            'exa': [],
            'serper': [],
            'serpapi': [],  # Nova API adicionada
            'tavily': [],
            'supadata': [],
            'firecrawl': [],
            'scrapingant': [],
            'youtube': [],
            'rapidapi': []  # Nova API adicionada
        }
        
        # Definir cadeias de fallback (cada grupo é uma prioridade)
        self.fallback_chains = {
            'ai_models': [['qwen'], ['gemini'], ['openai'], ['groq'], ['deepseek']],
            'search': [['jina'], ['exa'], ['serper'], ['serpapi'], ['firecrawl'], ['tavily']],
            'social_insights': [['supadata'], ['serper'], ['serpapi'], ['firecrawl'], ['tavily']],
            'web_scraping': [['firecrawl'], ['scrapingant'], ['jina'], ['serper'], ['serpapi']],
            'content_extraction': [['firecrawl'], ['jina'], ['scrapingant'], ['serper'], ['rapidapi']],
            'url_analysis': [['firecrawl'], ['jina'], ['exa'], ['serper'], ['serpapi']]
        }
        self.current_api_index = {}
        self.lock = threading.Lock()
        self.health_check_interval = 300  # 5 minutos
        self.last_health_check = {}
        
        self._load_api_configurations()
        self._initialize_health_monitoring()
    
    def _load_api_configurations(self):
        """Carrega configurações de APIs do .env"""
        try:
            # OpenRouter - Usar as chaves reais do .env na ordem correta
            openrouter_keys = [
                os.getenv('OPENROUTER_API_KEY'),
                os.getenv('OPENROUTER_API_KEY_1'), 
                os.getenv('OPENROUTER_API_KEY_2')
            ]
            
            for i, key in enumerate(openrouter_keys, 1):
                if key and key.strip():
                    self.apis['qwen'].append(APIEndpoint(
                        name=f"openrouter_{i}",
                        api_key=key,
                        base_url='https://openrouter.ai/api/v1',
                        max_requests_per_minute=100
                    ))
                    logger.info(f"✅ OpenRouter API {i} carregada")
            
            # Gemini - Usar as chaves reais do .env
            gemini_keys = [
                os.getenv('GEMINI_API_KEY'),
                os.getenv('GEMINI_API_KEY_1'),
                os.getenv('GEMINI_API_KEY_2')
            ]
            
            for i, key in enumerate(gemini_keys, 1):
                if key and key.strip():
                    self.apis['gemini'].append(APIEndpoint(
                        name=f"gemini_{i}",
                        api_key=key,
                        base_url="https://generativelanguage.googleapis.com/v1beta",
                        max_requests_per_minute=60
                    ))
                    logger.info(f"✅ Gemini API {i} carregada")
            
            # OpenAI
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self.apis['openai'].append(APIEndpoint(
                    name="openai_1",
                    api_key=openai_key,
                    base_url="https://api.openai.com/v1",
                    max_requests_per_minute=60
                ))
            
            # DeepSeek
            deepseek_key = os.getenv('DEEPSEEK_API_KEY')
            if deepseek_key:
                self.apis['deepseek'].append(APIEndpoint(
                    name="deepseek_1",
                    api_key=deepseek_key,
                    base_url="https://api.deepseek.com",
                    max_requests_per_minute=60
                ))
            
            # Jina AI - Primário para busca
            jina_keys = [
                os.getenv('JINA_API_KEY'),
                os.getenv('JINA_API_KEY_1')
            ]
            
            for i, key in enumerate(jina_keys, 1):
                if key and key.strip():
                    self.apis['jina'].append(APIEndpoint(
                        name=f"jina_{i}",
                        api_key=key,
                        base_url="https://r.jina.ai",
                        max_requests_per_minute=200
                    ))
                    logger.info(f"✅ Jina API {i} carregada")
            
            # EXA - Fallback para Jina
            exa_keys = [
                os.getenv('EXA_API_KEY'),
                os.getenv('EXA_API_KEY_1')
            ]
            
            for i, key in enumerate(exa_keys, 1):
                if key and key.strip():
                    self.apis['exa'].append(APIEndpoint(
                        name=f"exa_{i}",
                        api_key=key,
                        base_url="https://api.exa.ai",
                        max_requests_per_minute=100
                    ))
                    logger.info(f"✅ EXA API {i} carregada")
            
            # Serper - Substituto secundário
            serper_keys = [
                os.getenv('SERPER_API_KEY'),
                os.getenv('SERPER_API_KEY_1')
            ]
            
            for i, key in enumerate(serper_keys, 1):
                if key and key.strip():
                    self.apis['serper'].append(APIEndpoint(
                        name=f"serper_{i}",
                        api_key=key,
                        base_url="https://google.serper.dev",
                        max_requests_per_minute=100
                    ))
                    logger.info(f"✅ Serper API {i} carregada")
            
            # SerpAPI - Nova adição para busca Google
            serpapi_keys = [
                os.getenv('SERP_API_KEY'),
                os.getenv('SERP_API_KEY_1')
            ]
            
            for i, key in enumerate(serpapi_keys, 1):
                if key and key.strip():
                    self.apis['serpapi'].append(APIEndpoint(
                        name=f"serpapi_{i}",
                        api_key=key,
                        base_url="https://serpapi.com",
                        max_requests_per_minute=100
                    ))
                    logger.info(f"✅ SerpAPI {i} carregada")
            
            # Supadata - Para insights de redes sociais
            supadata_keys = [
                os.getenv('SUPADATA_API_KEY'),
                os.getenv('SUPADATA_API_KEY_1')
            ]
            
            for i, key in enumerate(supadata_keys, 1):
                if key and key.strip():
                    self.apis['supadata'].append(APIEndpoint(
                        name=f"supadata_{i}",
                        api_key=key,
                        base_url=os.getenv('SUPADATA_API_URL', 'https://api.supadata.ai/v1'),
                        max_requests_per_minute=50
                    ))
                    logger.info(f"✅ Supadata API {i} carregada")
            
            # Groq
            groq_keys = [
                os.getenv('GROQ_API_KEY'),
                os.getenv('GROQ_API_KEY_1')
            ]
            
            for i, key in enumerate(groq_keys, 1):
                if key and key.strip():
                    self.apis['groq'].append(APIEndpoint(
                        name=f"groq_{i}",
                        api_key=key,
                        base_url="https://api.groq.com/openai/v1",
                        max_requests_per_minute=30
                    ))
                    logger.info(f"✅ Groq API {i} carregada")
            
            # Tavily
            tavily_key = os.getenv('TAVILY_API_KEY')
            if tavily_key:
                self.apis['tavily'].append(APIEndpoint(
                    name="tavily_1",
                    api_key=tavily_key,
                    base_url="https://api.tavily.com",
                    max_requests_per_minute=100
                ))
            
            # Firecrawl
            firecrawl_keys = [
                os.getenv('FIRECRAWL_API_KEY'),
                os.getenv('FIRECRAWL_API_KEY_1')
            ]
            
            for i, key in enumerate(firecrawl_keys, 1):
                if key and key.strip():
                    self.apis['firecrawl'].append(APIEndpoint(
                        name=f"firecrawl_{i}",
                        api_key=key,
                        base_url="https://api.firecrawl.dev",
                        max_requests_per_minute=60
                    ))
                    logger.info(f"✅ Firecrawl API {i} carregada")
            
            # ScrapingAnt
            scrapingant_key = os.getenv('SCRAPINGANT_API_KEY')
            if scrapingant_key:
                self.apis['scrapingant'].append(APIEndpoint(
                    name="scrapingant_1",
                    api_key=scrapingant_key,
                    base_url="https://api.scrapingant.com",
                    max_requests_per_minute=60
                ))
            
            # YouTube
            youtube_key = os.getenv('YOUTUBE_API_KEY')
            if youtube_key:
                self.apis['youtube'].append(APIEndpoint(
                    name="youtube_1",
                    api_key=youtube_key,
                    base_url="https://www.googleapis.com/youtube/v3",
                    max_requests_per_minute=100
                ))
            
            # RapidAPI - Para APIs múltiplas
            rapidapi_key = os.getenv('RAPIDAPI_KEY')
            if rapidapi_key:
                self.apis['rapidapi'].append(APIEndpoint(
                    name="rapidapi_1",
                    api_key=rapidapi_key,
                    base_url="https://rapidapi.com",
                    max_requests_per_minute=200
                ))
                logger.info("✅ RapidAPI carregada")
            
            # Inicializar índices
            for service in self.apis:
                self.current_api_index[service] = 0
                
            total_apis = sum(len(apis) for apis in self.apis.values())
            logger.info(f"✅ APIs carregadas: {total_apis} endpoints")
            
            # Log detalhado das APIs carregadas
            for service, apis in self.apis.items():
                if apis:
                    logger.info(f"  - {service}: {len(apis)} APIs")
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar configurações de API: {e}")
    
    def _get_base_url(self, service: str) -> str:
        """Retorna URL base para cada serviço"""
        urls = {
            'tavily': 'https://api.tavily.com',
            'exa': 'https://api.exa.ai',
            'serpapi': 'https://serpapi.com/search',
            'rapidapi': 'https://rapidapi.com',
            'serper': 'https://google.serper.dev'
        }
        return urls.get(service, '')
    
    def _initialize_health_monitoring(self):
        """Inicializa monitoramento de saúde das APIs"""
        for service in self.apis:
            self.last_health_check[service] = datetime.now() - timedelta(minutes=10)
    
    def get_active_api(self, service: str, force_check: bool = False) -> Optional[APIEndpoint]:
        """
        Retorna API ativa para o serviço especificado com rotação automática
        """
        with self.lock:
            if service not in self.apis or not self.apis[service]:
                logger.warning(f"⚠️ Nenhuma API disponível para {service}")
                return None
            
            # Health check se necessário
            if force_check or self._needs_health_check(service):
                self._perform_health_check(service)
            
            # Encontrar API ativa com rotação automática
            apis = self.apis[service]
            start_index = self.current_api_index[service]
            
            # Verificar se a API atual está disponível
            current_api = apis[start_index]
            if self._is_api_available(current_api):
                current_api.last_used = datetime.now()
                current_api.requests_made += 1
                logger.info(f"🔄 Continuando com API {current_api.name} para {service}")
                return current_api
            
            # Se API atual não está disponível, rotar automaticamente
            logger.info(f"🔄 API atual indisponível, rotacionando {service}...")
            for i in range(1, len(apis)):  # Começar da próxima API
                index = (start_index + i) % len(apis)
                api = apis[index]
                
                if self._is_api_available(api):
                    self.current_api_index[service] = index
                    api.last_used = datetime.now()
                    api.requests_made += 1
                    logger.info(f"✅ Rotação automática: API {api.name} para {service}")
                    return api
            
            logger.error(f"❌ Nenhuma API disponível para {service} após rotação")
            return None
    
    def _needs_health_check(self, service: str) -> bool:
        """Verifica se precisa fazer health check"""
        last_check = self.last_health_check.get(service)
        if not last_check:
            return True
        return datetime.now() - last_check > timedelta(seconds=self.health_check_interval)
    
    def _perform_health_check(self, service: str):
        """Executa health check nas APIs do serviço"""
        try:
            for api in self.apis[service]:
                if api.status == APIStatus.OFFLINE:
                    continue
                
                # Reset rate limit se expirou
                if api.rate_limit_reset and datetime.now() > api.rate_limit_reset:
                    api.status = APIStatus.ACTIVE
                    api.rate_limit_reset = None
                    api.requests_made = 0
                
                # Verificar se está rate limited
                if api.requests_made >= api.max_requests_per_minute:
                    api.status = APIStatus.RATE_LIMITED
                    api.rate_limit_reset = datetime.now() + timedelta(minutes=1)
            
            self.last_health_check[service] = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Erro no health check de {service}: {e}")
    
    def _is_api_available(self, api: APIEndpoint) -> bool:
        """Verifica se API está disponível para uso"""
        if api.status == APIStatus.OFFLINE:
            return False
        
        if api.status == APIStatus.RATE_LIMITED:
            if api.rate_limit_reset and datetime.now() > api.rate_limit_reset:
                api.status = APIStatus.ACTIVE
                api.requests_made = 0
                return True
            return False
        
        if api.status == APIStatus.ERROR and api.error_count > 5:
            return False
        
        return True
    
    def mark_api_error(self, service: str, api_name: str, error: Exception):
        """Marca API como com erro e força rotação imediata"""
        with self.lock:
            for i, api in enumerate(self.apis[service]):
                if api.name == api_name:
                    api.error_count += 1
                    api.status = APIStatus.ERROR
                    
                    # Se muitos erros, marca como offline temporariamente
                    if api.error_count >= 3:
                        api.status = APIStatus.OFFLINE
                        api.rate_limit_reset = datetime.now() + timedelta(minutes=5)
                    
                    # Força rotação para próxima API
                    self.current_api_index[service] = (i + 1) % len(self.apis[service])
                    
                    logger.warning(f"⚠️ API {api_name} marcada com erro: {error}")
                    logger.info(f"🔄 Rotação forçada para {service}")
                    break
    
    def get_fallback_api(self, service_type: str) -> Optional[APIEndpoint]:
        """
        Obtém API de fallback baseada nas cadeias de prioridade
        """
        if service_type not in self.fallback_chains:
            return None
        
        # Tenta cada cadeia de fallback em ordem de prioridade
        for chain in self.fallback_chains[service_type]:
            for service in chain:
                api = self.get_active_api(service)
                if api:
                    logger.info(f"🔄 Fallback ativado: {service} para {service_type}")
                    return api
        
        logger.error(f"❌ Nenhum fallback disponível para {service_type}")
        return None
    
    def rotate_api(self, service: str) -> Optional[APIEndpoint]:
        """
        Força rotação manual para próxima API disponível
        """
        with self.lock:
            if service not in self.apis or not self.apis[service]:
                return None
            
            apis = self.apis[service]
            current_index = self.current_api_index[service]
            
            # Tenta próximas APIs
            for i in range(1, len(apis)):
                next_index = (current_index + i) % len(apis)
                api = apis[next_index]
                
                if self._is_api_available(api):
                    self.current_api_index[service] = next_index
                    api.last_used = datetime.now()
                    logger.info(f"🔄 Rotação manual: {api.name} para {service}")
                    return api
            
            return None
    
    def get_api_status(self, service: str = None) -> Dict[str, Any]:
        """
        Retorna status detalhado das APIs
        """
        if service:
            if service not in self.apis:
                return {}
            
            apis_status = []
            for api in self.apis[service]:
                apis_status.append({
                    'name': api.name,
                    'status': api.status.value,
                    'error_count': api.error_count,
                    'requests_made': api.requests_made,
                    'max_requests': api.max_requests_per_minute,
                    'last_used': api.last_used.isoformat() if api.last_used else None,
                    'rate_limit_reset': api.rate_limit_reset.isoformat() if api.rate_limit_reset else None
                })
            
            return {
                'service': service,
                'current_api_index': self.current_api_index.get(service, 0),
                'apis': apis_status
            }
        
        # Status de todos os serviços
        all_status = {}
        for svc in self.apis:
            all_status[svc] = self.get_api_status(svc)
        
        return all_status
    
    def update_api_key(self, service: str, api_name: str, new_key: str) -> bool:
        """
        Atualiza chave de API em tempo real
        """
        with self.lock:
            for api in self.apis[service]:
                if api.name == api_name:
                    api.api_key = new_key
                    api.status = APIStatus.ACTIVE
                    api.error_count = 0
                    api.requests_made = 0
                    logger.info(f"🔑 Chave atualizada para {api_name}")
                    return True
        return False
    
    def add_api_key(self, service: str, api_key: str, base_url: str = None) -> str:
        """
        Adiciona nova chave de API dinamicamente
        """
        with self.lock:
            api_name = f"{service}_{len(self.apis[service]) + 1}"
            
            new_api = APIEndpoint(
                name=api_name,
                api_key=api_key,
                base_url=base_url or self._get_base_url(service),
                max_requests_per_minute=60
            )
            
            self.apis[service].append(new_api)
            logger.info(f"➕ Nova API adicionada: {api_name}")
            return api_name
    
    def remove_api_key(self, service: str, api_name: str) -> bool:
        """
        Remove chave de API
        """
        with self.lock:
            for i, api in enumerate(self.apis[service]):
                if api.name == api_name:
                    del self.apis[service][i]
                    # Ajusta índice atual se necessário
                    if self.current_api_index[service] >= len(self.apis[service]):
                        self.current_api_index[service] = 0
                    logger.info(f"➖ API removida: {api_name}")
                    return True
        return False
    
    def reset_api_errors(self, service: str = None):
        """
        Reseta contadores de erro das APIs
        """
        with self.lock:
            services = [service] if service else self.apis.keys()
            
            for svc in services:
                for api in self.apis[svc]:
                    api.error_count = 0
                    if api.status == APIStatus.ERROR:
                        api.status = APIStatus.ACTIVE
            
            logger.info(f"🔄 Erros resetados para {service or 'todos os serviços'}")
    
    def get_next_available_api(self, service: str) -> Optional[APIEndpoint]:
        """
        Obtém próxima API disponível sem alterar o índice atual
        """
        if service not in self.apis or not self.apis[service]:
            return None
        
        apis = self.apis[service]
        current_index = self.current_api_index[service]
        
        # Verifica próximas APIs sem alterar estado
        for i in range(len(apis)):
            index = (current_index + i) % len(apis)
            api = apis[index]
            
            if self._is_api_available(api):
                return api
        
        return None

# Instância global
enhanced_api_rotation_manager = EnhancedAPIRotationManager()

def get_api_manager() -> EnhancedAPIRotationManager:
    """Retorna instância do gerenciador de APIs"""
    return enhanced_api_rotation_manager