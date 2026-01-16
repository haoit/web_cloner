#!/usr/bin/env python3
"""
Website Cloner - Download toàn bộ website bao gồm tất cả tài nguyên static
Tự động download và cập nhật đường dẫn để có thể chạy offline hoàn toàn
"""

import os
import re
import sys
import hashlib
import mimetypes
from urllib.parse import urljoin, urlparse, unquote
from pathlib import Path
from collections import deque
import argparse

import requests
from bs4 import BeautifulSoup


class WebsiteCloner:
    def __init__(self, base_url, output_dir="cloned_site", max_depth=3, download_all_external=True):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.output_dir = Path(output_dir)
        self.max_depth = max_depth
        self.download_all_external = download_all_external  # Download tất cả resources từ external domains
        
        # Các domain cần loại bỏ hoàn toàn (không download, không giữ link)
        # Bao gồm các CDN phổ biến mà ta muốn clone resources về local
        self.external_cdn_domains = [
            'ladicdn.com', 'w.ladicdn.com', 's.ladicdn.com',
            'cdn.ladicdn.com', 'static.ladipage.net',
            'a.ladipage.com', 'api1.ldpform.com', 'api.sales.ldpform.net'
        ]
        
        # Các domain cho preconnect/dns-prefetch cần loại bỏ
        self.remove_preconnect_domains = [
            'ladicdn.com', 'ladipage.com', 'ldpform.com', 'ldpform.net',
            'fonts.googleapis.com', 'fonts.gstatic.com'
        ]
        
        # Tracking
        self.downloaded_urls = set()
        self.url_mapping = {}  # Map original URL to local path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Tạo thư mục output
        self.create_directories()
    
    def is_external_cdn(self, url):
        """Kiểm tra xem URL có thuộc external CDN cần clone về local không"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        for cdn in self.external_cdn_domains:
            if cdn in domain:
                return True
        return False
    
    def should_remove_preconnect(self, url):
        """Kiểm tra xem preconnect/dns-prefetch có nên bị loại bỏ không"""
        if not url:
            return False
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        for d in self.remove_preconnect_domains:
            if d in domain:
                return True
        return False
    
    def create_directories(self):
        """Tạo cấu trúc thư mục - index.html sẽ ở root"""
        directories = [
            self.output_dir,
            self.output_dir / 'css',
            self.output_dir / 'js',
            self.output_dir / 'images',
            self.output_dir / 'fonts',
            self.output_dir / 'media',
            self.output_dir / 'other'
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_resource_type(self, url, content_type=None):
        """Xác định loại tài nguyên dựa vào URL và content-type"""
        url_lower = url.lower()
        
        # Kiểm tra extension
        if any(url_lower.endswith(ext) for ext in ['.css']):
            return 'css'
        elif any(url_lower.endswith(ext) for ext in ['.js']):
            return 'js'
        elif any(url_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp']):
            return 'images'
        elif any(url_lower.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf']):
            return 'fonts'
        elif any(url_lower.endswith(ext) for ext in ['.mp4', '.webm', '.ogg', '.mp3', '.wav']):
            return 'media'
        
        # Kiểm tra content-type
        if content_type:
            if 'text/css' in content_type:
                return 'css'
            elif 'javascript' in content_type:
                return 'js'
            elif 'image' in content_type:
                return 'images'
            elif 'font' in content_type:
                return 'fonts'
            elif 'video' in content_type or 'audio' in content_type:
                return 'media'
        
        return 'other'
    
    def generate_local_filename(self, url, resource_type):
        """Tạo tên file local duy nhất"""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        # Tạo hash ngắn từ URL để tránh trùng lặp
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Lấy tên file gốc
        if path and path != '/':
            filename = os.path.basename(path)
            if not filename:
                filename = f'resource_{url_hash}'
        else:
            filename = f'resource_{url_hash}'
        
        # Thêm extension nếu thiếu
        if '.' not in filename:
            ext_map = {
                'css': '.css',
                'js': '.js',
                'images': '.png',
                'fonts': '.woff2',
                'media': '.mp4'
            }
            filename += ext_map.get(resource_type, '.bin')
        
        # Tạo tên unique
        base_filename = filename
        counter = 1
        local_path = self.output_dir / resource_type / filename
        
        while local_path.exists() and local_path.read_bytes() != b'':
            name, ext = os.path.splitext(base_filename)
            filename = f"{name}_{counter}{ext}"
            local_path = self.output_dir / resource_type / filename
            counter += 1
        
        return local_path
    
    def download_resource(self, url, is_main_page=False):
        """Download một tài nguyên"""
        if url in self.downloaded_urls:
            return self.url_mapping.get(url)
        
        try:
            print(f"Downloading: {url}")
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            
            # Nếu là trang chính, lưu vào root với tên index.html
            if is_main_page:
                local_path = self.output_dir / 'index.html'
            else:
                resource_type = self.get_resource_type(url, content_type)
                local_path = self.generate_local_filename(url, resource_type)
            
            # Lưu file
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.downloaded_urls.add(url)
            self.url_mapping[url] = local_path
            
            print(f"  → Saved to: {local_path}")
            return local_path
            
        except Exception as e:
            print(f"  ✗ Error downloading {url}: {e}")
            return None
    
    def extract_urls_from_css(self, css_content, base_url):
        """Trích xuất URLs từ CSS (url(...))"""
        urls = []
        # Pattern cải tiến: url('...'), url("..."), url(...)
        # Group 2 là nội dung URL
        matches = re.finditer(r'url\(\s*(["\']?)(.*?)\1\s*\)', css_content, re.IGNORECASE)
        
        for match in matches:
            match_str = match.group(2).strip()
            # Bỏ qua data URIs và empty
            if match_str.startswith('data:') or not match_str:
                continue
            
            # Resolve relative URL
            absolute_url = urljoin(base_url, match_str)
            urls.append((match_str, absolute_url))
    
        return urls
    
    def process_css(self, css_path, original_url):
        """Xử lý file CSS và download tài nguyên bên trong"""
        try:
            with open(css_path, 'r', encoding='utf-8', errors='ignore') as f:
                css_content = f.read()
            
            urls = self.extract_urls_from_css(css_content, original_url)
            
            for original_ref, absolute_url in urls:
                # Download resource
                local_path = self.download_resource(absolute_url)
                
                if local_path:
                    # Tính relative path từ CSS file đến resource
                    relative_path = os.path.relpath(local_path, css_path.parent)
                    relative_path = relative_path.replace('\\', '/')
                    
                    # Simple string replace
                    css_content = css_content.replace(original_ref, relative_path)
            
            # Lưu CSS đã cập nhật
            with open(css_path, 'w', encoding='utf-8') as f:
                f.write(css_content)
                
        except Exception as e:
            print(f"Error processing CSS {css_path}: {e}")
    
    def process_inline_style(self, style_content, base_url, html_path):
        """Xử lý inline CSS trong <style> tags - download cả external URLs"""
        try:
            urls = self.extract_urls_from_css(style_content, base_url)
            print(f"    DEBUG: Found {len(urls)} URLs in inline style")
            
            for original_ref, absolute_url in urls:
                print(f"    DEBUG: Processing URL: {absolute_url[:60]}...")
                # Download resource (bao gồm cả external CDN)
                local_path = self.download_resource(absolute_url)
                
                if local_path:
                    # Tính relative path từ HTML file đến resource
                    relative_path = os.path.relpath(local_path, html_path.parent)
                    relative_path = relative_path.replace('\\', '/')
                    
                    # Quan trọng: Cần escape đúng các ký tự đặc biệt trong URL
                    escaped_ref = re.escape(original_ref)
                    
                    # Simple string replace
                    if original_ref in style_content:
                        style_content = style_content.replace(original_ref, relative_path)
                        print(f"    ✓ Replaced in CSS: {original_ref[:40]}... → {relative_path}")
                    else:
                        print(f"    ✗ URL not found in content: {original_ref[:40]}...")
            
            return style_content
            
        except Exception as e:
            print(f"Error processing inline style: {e}")
            import traceback
            traceback.print_exc()
            return style_content
    
    def process_html(self, html_path, original_url):
        """Xử lý file HTML và download tất cả tài nguyên"""
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            # ========== BƯỚC 1: Loại bỏ preconnect/dns-prefetch/preload tới external domains ==========
            print("  → Cleaning up external preconnect/preload tags...")
            
            # Loại bỏ dns-prefetch tags
            for tag in soup.find_all('link', rel='dns-prefetch'):
                tag.decompose()
            
            # Loại bỏ preconnect tags tới external domains
            for tag in soup.find_all('link', rel='preconnect'):
                href = tag.get('href', '')
                if self.should_remove_preconnect(href):
                    print(f"    ✗ Removed preconnect: {href}")
                    tag.decompose()
            
            # Loại bỏ preload tới external scripts/styles
            for tag in soup.find_all('link', rel='preload'):
                href = tag.get('href', '')
                if href and (self.is_external_cdn(href) or self.should_remove_preconnect(href)):
                    print(f"    ✗ Removed preload: {href}")
                    tag.decompose()
            
            # ========== BƯỚC 2: Xử lý INLINE <style> tags (QUAN TRỌNG!) ==========
            print("  → Processing inline <style> tags...")
            from bs4 import NavigableString
            for style_tag in soup.find_all('style'):
                # Sử dụng get_text() thay vì .string để đảm bảo lấy được nội dung ngay cả khi có comments
                style_content = style_tag.get_text()
                if style_content:
                    updated_style = self.process_inline_style(style_content, original_url, html_path)
                    if updated_style != style_content:
                        # Cập nhật nội dung bằng cách clear và append NavigableString
                        style_tag.clear()
                        style_tag.append(NavigableString(updated_style))
                        print(f"    ✓ Updated style block id={style_tag.get('id', 'unknown')}")
            
            # Download và thay thế CSS external
            for tag in soup.find_all('link', rel='stylesheet'):
                if tag.get('href'):
                    css_url = urljoin(original_url, tag['href'])
                    local_path = self.download_resource(css_url)
                    
                    if local_path:
                        relative_path = os.path.relpath(local_path, html_path.parent)
                        tag['href'] = relative_path.replace('\\', '/')
                        
                        # Process CSS để download fonts, images trong CSS
                        self.process_css(local_path, css_url)
            
            # Download và thay thế JS
            for tag in soup.find_all('script', src=True):
                js_url = urljoin(original_url, tag['src'])
                local_path = self.download_resource(js_url)
                
                if local_path:
                    relative_path = os.path.relpath(local_path, html_path.parent)
                    tag['src'] = relative_path.replace('\\', '/')
            
            # Download và thay thế images
            for tag in soup.find_all('img', src=True):
                img_url = urljoin(original_url, tag['src'])
                local_path = self.download_resource(img_url)
                
                if local_path:
                    relative_path = os.path.relpath(local_path, html_path.parent)
                    tag['src'] = relative_path.replace('\\', '/')
            
            # Download srcset images
            for tag in soup.find_all('img', srcset=True):
                srcset = tag['srcset']
                new_srcset = []
                
                for item in srcset.split(','):
                    parts = item.strip().split()
                    if parts:
                        img_url = urljoin(original_url, parts[0])
                        local_path = self.download_resource(img_url)
                        
                        if local_path:
                            relative_path = os.path.relpath(local_path, html_path.parent)
                            parts[0] = relative_path.replace('\\', '/')
                        
                        new_srcset.append(' '.join(parts))
                
                tag['srcset'] = ', '.join(new_srcset)
            
            # Download background images từ inline style attributes
            for tag in soup.find_all(style=True):
                style = tag['style']
                urls = self.extract_urls_from_css(style, original_url)
                
                for original_ref, absolute_url in urls:
                    local_path = self.download_resource(absolute_url)
                    
                    if local_path:
                        relative_path = os.path.relpath(local_path, html_path.parent)
                        relative_path = relative_path.replace('\\', '/')
                        
                        style = re.sub(
                            r'url\(\s*["\']?' + re.escape(original_ref) + r'["\']?\s*\)',
                            f'url("{relative_path}")',
                            style
                        )
                
                tag['style'] = style
            
            # Download video/audio sources
            for tag in soup.find_all(['video', 'audio']):
                if tag.get('src'):
                    media_url = urljoin(original_url, tag['src'])
                    local_path = self.download_resource(media_url)
                    
                    if local_path:
                        relative_path = os.path.relpath(local_path, html_path.parent)
                        tag['src'] = relative_path.replace('\\', '/')
                
                for source in tag.find_all('source', src=True):
                    media_url = urljoin(original_url, source['src'])
                    local_path = self.download_resource(media_url)
                    
                    if local_path:
                        relative_path = os.path.relpath(local_path, html_path.parent)
                        source['src'] = relative_path.replace('\\', '/')
            
            # Download favicon
            for tag in soup.find_all('link', rel=lambda x: x and 'icon' in str(x).lower()):
                if tag.get('href'):
                    icon_url = urljoin(original_url, tag['href'])
                    local_path = self.download_resource(icon_url)
                    
                    if local_path:
                        relative_path = os.path.relpath(local_path, html_path.parent)
                        tag['href'] = relative_path.replace('\\', '/')

            # Download SVG images (<image href="..."> và <use href="...">)
            # Lưu ý: SVG có thể dùng href (SVG 2) hoặc xlink:href (SVG 1.1)
            for tag in soup.find_all(['image', 'use']):
                # Kiểm tra cả href và xlink:href
                for attr in ['href', 'xlink:href']:
                    if tag.has_attr(attr):
                        url = tag[attr]
                        # Bỏ qua reference ID nội bộ (bắt đầu bằng #)
                        if url.startswith('#') or url.startswith('data:'):
                            continue
                            
                        full_url = urljoin(original_url, url)
                        local_path = self.download_resource(full_url)
                        
                        if local_path:
                            relative_path = os.path.relpath(local_path, html_path.parent)
                            tag[attr] = relative_path.replace('\\', '/')
                            print(f"    ✓ Replaced SVG {tag.name}: {url} → {relative_path.replace('\\', '/')}")
            
            # ========== BƯỚC BONUS: Xử lý URLs trong INLINE SCRIPTs ==========
            print("  → Processing inline <script> tags for external URLs...")
            for script_tag in soup.find_all('script'):
                if script_tag.string:
                     content = str(script_tag.string)
                     # Tìm các URL trong script (đơn giản, bắt đầu bằng http/https)
                     # Group 1: Quote (hoặc rỗng), Group 2: URL
                     urls = re.findall(r'(["\'])(https?://[^"\'\s<>]+)\1', content)
                     modified = False
                     for quote, url in urls:
                         if self.is_external_cdn(url):
                             # Nếu là file resource (ảnh, script...), download
                             path = urlparse(url).path
                             if path and '.' in os.path.basename(path):
                                 local_path = self.download_resource(url)
                                 if local_path:
                                     relative_path = os.path.relpath(local_path, html_path.parent).replace('\\', '/')
                                     content = content.replace(url, relative_path)
                                     modified = True
                                     print(f"    ✓ Replaced in JS: {url} → {relative_path}")
                             else:
                                 # Nếu là domain root, replace bằng '.' để trỏ về local
                                 content = content.replace(url, '.')
                                 modified = True
                                 print(f"    ✓ Replaced CDN root in JS: {url} → .")
                     
                     if modified:
                         script_tag.string = content

            # Lưu HTML đã cập nhật (không dùng prettify để tránh mất modifications)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            # ========== POST-PROCESSING: Replace remaining CDN URLs ==========
            print("  → Post-processing: Replacing any remaining CDN URLs...")
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Tìm tất cả URLs từ external CDN domains còn sót lại
            for domain in self.external_cdn_domains:
                # Pattern: https://domain/path/to/file.ext
                pattern = rf'https?://[^/]*{re.escape(domain)}[^"\'\s<>)]*'
                matches = re.findall(pattern, html_content)
                
                for url in set(matches):  # Use set to avoid duplicates
                    # Kiểm tra xem file đã được download chưa
                    if url in self.url_mapping:
                        local_path = self.url_mapping[url]
                        relative_path = os.path.relpath(local_path, html_path.parent).replace('\\', '/')
                        html_content = html_content.replace(url, relative_path)
                        print(f"    ✓ Post-replaced: {url[:50]}... → {relative_path}")
                    else:
                        # Nếu chưa download (có thể là domain root), replace bằng '.'
                        html_content = html_content.replace(url, '.')
                        print(f"    ✓ Post-replaced CDN root: {url}")
            
            # Save lại file sau post-processing
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✓ Processed HTML: {html_path}")
            
        except Exception as e:
            print(f"Error processing HTML {html_path}: {e}")
    
    def clone(self):
        """Clone toàn bộ website"""
        print(f"\n{'='*60}")
        print(f"Starting website clone: {self.base_url}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'='*60}\n")
        
        # Download trang chính vào root/index.html
        main_html_path = self.download_resource(self.base_url, is_main_page=True)
        
        if not main_html_path:
            print("Failed to download main page!")
            return
        
        # Process HTML để download tất cả resources
        self.process_html(main_html_path, self.base_url)
        
        print(f"\n{'='*60}")
        print(f"✓ Clone completed!")
        print(f"  Total files downloaded: {len(self.downloaded_urls)}")
        print(f"  Main file: {main_html_path}")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Clone toàn bộ website bao gồm tất cả tài nguyên static',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python website_cloner.py https://example.com
  python website_cloner.py https://example.com -o my_site
  python website_cloner.py https://example.com -o my_site -d 5
        """
    )
    
    parser.add_argument('url', help='URL của website cần clone')
    parser.add_argument('-o', '--output', default=None, 
                       help='Thư mục output (mặc định: tên domain của website)')
    parser.add_argument('-d', '--depth', type=int, default=3,
                       help='Độ sâu crawl (mặc định: 3)')
    
    args = parser.parse_args()
    
    # Kiểm tra URL
    if not args.url.startswith(('http://', 'https://')):
        print("Error: URL phải bắt đầu với http:// hoặc https://")
        sys.exit(1)
    
    # Tự động xác định thư mục output nếu không được cung cấp
    output_dir = args.output
    if output_dir is None:
        parsed = urlparse(args.url)
        domain = parsed.netloc
        # Xử lý tên thư mục an toàn cho Windows (bỏ ký tự :)
        safe_domain = domain.replace(':', '_')
        output_dir = safe_domain
        print(f"Output directory not specified. Using domain name: {output_dir}")
    
    # Bắt đầu clone
    cloner = WebsiteCloner(args.url, output_dir, args.depth)
    cloner.clone()
    
    print(f"\nMở file sau để xem kết quả:")
    print(f"  file://{os.path.abspath(cloner.output_dir / 'index.html')}")


if __name__ == '__main__':
    main()