import json
import re
import uuid
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI


class ScienceTeacher:
    def __init__(self, api_key: str, tts_service):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-flash-latest",
            google_api_key=api_key,
            temperature=0.5,
        )
        self.tts = tts_service

    def _extract_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, str):
                    parts.append(c)
                elif isinstance(c, dict) and "text" in c:
                    parts.append(c["text"])
                else:
                    parts.append(str(c))
            return "".join(parts)
        return str(content)

    def generate_simulation(self, page_text: str) -> dict:
        """Sayfa metninden Canvas animasyon kodu dahil deney simülasyonu üret"""

        prompt = f"""Sen bir fen bilimleri deney simülasyonu uzmanısın ve HTML5 Canvas programcısısın.

Aşağıdaki ders kitabı sayfasındaki konuyu analiz et ve o konuyla ilgili bir deney simülasyonu hazırla.

"canvas_code" alanında deneyi GÖRSEL olarak canlandıran bir JavaScript fonksiyonu yaz.
Fonksiyon: function drawLab(ctx, W, step) {{ ... }}
Parametreler: ctx=Canvas 2D context, W=760 (genişlik), step=0,1,2,3 (adım numarası)

KRİTİK KURALLAR:
1. Her step tamamen BAĞIMSIZ bir sahne olmalı — if(step===0){{...}} else if(step===1){{...}} yapısı kullan
2. Her step içinde o adıma ait TÜM çizimleri yap (masa, ekipman, sıvı, etiket)
3. Date.now() KULLANMA — statik sahneler çiz
4. ctx.save()/ctx.restore() KULLANMA
5. Basit geometrik şekillerle laboratuvar ekipmanları çiz (beher=dikdörtgen, tüp=dar dikdörtgen, sıvı=renkli dolgulu dikdörtgen)
6. Her adımda başlık yaz

Türkçe yaz. SADECE geçerli JSON döndür, markdown yok.

Sayfa metni:
{page_text[:3000]}

JSON formatı:
{{
  "title": "Deney başlığı",
  "subject": "fizik/kimya/biyoloji",
  "topic": "Konu adı",
  "description": "Kısa açıklama",
  "materials": [{{"name": "Malzeme", "icon": "🧪", "quantity": "Miktar"}}],
  "safety": [{{"warning": "Uyarı", "icon": "⚠️"}}],
  "total_steps": 4,
  "steps": [
    {{"step": 0, "title": "Adım başlığı", "description": "Açıklama", "observation": "Gözlem"}}
  ],
  "canvas_code": "function drawLab(ctx, canvas, step) {{ ctx.clearRect(0,0,canvas.width,canvas.height); /* ... çizim kodu ... */ }}",
  "result": {{
    "what_happened": "Ne oldu?",
    "why": "Neden oldu?",
    "formula": "Formül",
    "real_life": "Günlük hayat"
  }},
  "chemical_reaction": {{
    "has_reaction": true,
    "equation": "Denklem",
    "type": "Reaksiyon tipi"
  }}
}}"""

        try:
            raw = self.llm.invoke(prompt).content
            response = self._extract_text(raw)
            response = response.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', response, re.DOTALL)
            result = json.loads(match.group()) if match else json.loads(response)
        except Exception as e:
            print(f"Simülasyon üretme hatası: {e}")
            result = self._fallback_simulation(page_text)

        # Her adım için sesli anlatım
        for step in result.get("steps", []):
            text = f"Adım {step.get('step', 0) + 1}: {step.get('title', '')}. {step.get('description', '')}"
            fname = f"sim_step_{uuid.uuid4().hex[:8]}.mp3"
            audio = self.tts.text_to_speech(text, fname)
            step["audio_path"] = f"/audio/{Path(audio).name}"

        # Sonuç sesli anlatım
        res = result.get("result", {})
        if res.get("what_happened"):
            summary = f"Sonuç: {res['what_happened']}. {res.get('why', '')}"
            fname = f"sim_result_{uuid.uuid4().hex[:8]}.mp3"
            audio = self.tts.text_to_speech(summary, fname)
            result["result_audio"] = f"/audio/{Path(audio).name}"

        return result

    def _fallback_simulation(self, page_text: str) -> dict:
        words = page_text.lower()
        if any(w in words for w in ["hücre", "mitoz", "mayoz", "dna", "protein", "biyoloji"]):
            return self._bio_fallback()
        elif any(w in words for w in ["asit", "baz", "element", "bileşik", "mol", "kimya", "reaksiyon"]):
            return self._chem_fallback()
        else:
            return self._physics_fallback()

    def _chem_fallback(self):
        return {
            "title": "Asit-Baz Nötrleşme Deneyi",
            "subject": "kimya",
            "topic": "Asit-Baz Reaksiyonları",
            "description": "HCl asidi ile NaOH bazının nötrleşme reaksiyonu",
            "materials": [
                {"name": "HCl çözeltisi", "icon": "🧪", "quantity": "50 ml"},
                {"name": "NaOH çözeltisi", "icon": "⚗️", "quantity": "50 ml"},
                {"name": "Turnusol indikatörü", "icon": "💧", "quantity": "5 damla"},
                {"name": "Beher", "icon": "🥃", "quantity": "2 adet"},
            ],
            "safety": [{"warning": "Koruyucu gözlük ve eldiven takın. Asit ve bazlarla dikkatli çalışın.", "icon": "⚠️"}],
            "total_steps": 4,
            "steps": [
                {"step": 0, "title": "Asit Hazırlama", "description": "Behere 50 ml HCl çözeltisi koyun.", "observation": "Renksiz bir çözelti"},
                {"step": 1, "title": "İndikatör Ekleme", "description": "Turnusol indikatörü ekleyin.", "observation": "Çözelti kırmızıya döner"},
                {"step": 2, "title": "Baz Ekleme", "description": "Yavaşça NaOH çözeltisi ekleyin ve karıştırın.", "observation": "Renk değişmeye başlar"},
                {"step": 3, "title": "Nötrleşme", "description": "Eklemeye devam edin.", "observation": "Çözelti yeşile döner — nötr nokta"},
            ],
            "canvas_code": """function drawLab(ctx, W, step) {
var H=400;
ctx.fillStyle='#f5f5f5';ctx.fillRect(0,0,W,H);
ctx.fillStyle='#8d6e63';ctx.fillRect(0,320,W,80);
ctx.fillStyle='#6d4c41';ctx.fillRect(0,320,W,4);
var titles=['1. Asit Hazirlama','2. Indikator Ekleme','3. Baz Ekleme','4. Notrlesme'];
ctx.fillStyle='#1a237e';ctx.font='bold 18px sans-serif';ctx.fillText(titles[step]||'',250,30);
if(step===0){
  ctx.strokeStyle='#90a4ae';ctx.lineWidth=3;
  ctx.strokeRect(300,180,120,130);
  ctx.fillStyle='rgba(180,220,255,0.5)';ctx.fillRect(303,210,114,97);
  ctx.fillStyle='#333';ctx.font='14px sans-serif';ctx.fillText('HCl (50ml)',320,175);
  ctx.fillStyle='#1565c0';ctx.font='13px sans-serif';ctx.fillText('Renksiz cozelti',310,260);
} else if(step===1){
  ctx.strokeStyle='#90a4ae';ctx.lineWidth=3;
  ctx.strokeRect(300,180,120,130);
  ctx.fillStyle='#e53935';ctx.fillRect(303,220,114,87);
  ctx.fillStyle='#333';ctx.font='14px sans-serif';ctx.fillText('HCl + Turnusol',305,175);
  ctx.fillStyle='#fff';ctx.font='bold 14px sans-serif';ctx.fillText('pH < 7',335,265);
  ctx.fillStyle='#e53935';ctx.beginPath();ctx.arc(360,200,6,0,Math.PI*2);ctx.fill();
  ctx.beginPath();ctx.moveTo(360,194);ctx.lineTo(356,186);ctx.lineTo(364,186);ctx.closePath();ctx.fill();
  ctx.fillStyle='#333';ctx.font='12px sans-serif';ctx.fillText('Turnusol damlasi',320,155);
} else if(step===2){
  ctx.strokeStyle='#90a4ae';ctx.lineWidth=3;
  ctx.strokeRect(300,180,120,130);
  ctx.fillStyle='#ff9800';ctx.fillRect(303,210,114,97);
  ctx.fillStyle='#333';ctx.font='14px sans-serif';ctx.fillText('Karisim',335,175);
  ctx.fillStyle='#fff';ctx.font='bold 14px sans-serif';ctx.fillText('pH ~ 7',335,260);
  ctx.strokeRect(540,160,80,130);
  ctx.fillStyle='rgba(100,140,255,0.4)';ctx.fillRect(543,200,74,87);
  ctx.fillStyle='#333';ctx.font='14px sans-serif';ctx.fillText('NaOH',555,155);
  ctx.strokeStyle='rgba(100,140,255,0.6)';ctx.lineWidth=3;
  ctx.beginPath();ctx.moveTo(570,200);ctx.quadraticCurveTo(480,140,370,185);ctx.stroke();
} else if(step===3){
  ctx.strokeStyle='#90a4ae';ctx.lineWidth=3;
  ctx.strokeRect(300,180,120,130);
  ctx.fillStyle='#4caf50';ctx.fillRect(303,210,114,97);
  ctx.fillStyle='#fff';ctx.font='bold 16px sans-serif';ctx.fillText('pH = 7',330,260);
  ctx.fillStyle='#333';ctx.font='14px sans-serif';ctx.fillText('Notr cozelti',315,175);
  ctx.fillStyle='#4caf50';ctx.font='bold 20px sans-serif';ctx.fillText('Notrlesti!',320,370);
  ctx.fillStyle='#1a237e';ctx.font='14px sans-serif';ctx.fillText('HCl + NaOH -> NaCl + H2O',260,395);
}
}""",
            "result": {
                "what_happened": "Asit ve baz birleşerek tuz ve su oluşturdu. İndikatör rengi kırmızıdan yeşile döndü.",
                "why": "H⁺ iyonları (asit) ve OH⁻ iyonları (baz) birleşerek su (H₂O) oluşturur. Bu nötrleşme reaksiyonudur.",
                "formula": "HCl + NaOH → NaCl + H₂O",
                "real_life": "Mide yanmasında antiasit ilaçlar, toprak pH düzenlemesi, sabun üretimi"
            },
            "chemical_reaction": {"has_reaction": True, "equation": "HCl + NaOH → NaCl + H₂O", "type": "Nötrleşme"},
        }

    def _bio_fallback(self):
        return {
            "title": "Mikroskopla Hücre Gözlemi",
            "subject": "biyoloji",
            "topic": "Hücre Yapısı",
            "description": "Soğan zarı hücrelerinin mikroskop altında incelenmesi",
            "materials": [
                {"name": "Soğan", "icon": "🧅", "quantity": "1 adet"},
                {"name": "Mikroskop", "icon": "🔬", "quantity": "1 adet"},
                {"name": "Metilen mavisi", "icon": "💧", "quantity": "Birkaç damla"},
                {"name": "Lam-lamel", "icon": "📋", "quantity": "1 set"},
            ],
            "safety": [{"warning": "Mikroskop lamlarını dikkatli kullanın, kırılabilir.", "icon": "⚠️"}],
            "total_steps": 4,
            "steps": [
                {"step": 0, "title": "Kesit Alma", "description": "Soğan zarından ince bir kesit alın.", "observation": "İnce saydam tabaka"},
                {"step": 1, "title": "Lama Yerleştirme", "description": "Kesiti lam üzerine yerleştirin ve su damlatın.", "observation": "Kesit düzleşir"},
                {"step": 2, "title": "Boyama", "description": "Metilen mavisi damlatın ve lamel ile kapatın.", "observation": "Mavi renk yayılır"},
                {"step": 3, "title": "Mikroskop Gözlemi", "description": "40x büyütme ile inceleyin.", "observation": "Hücre duvarı, çekirdek ve sitoplazma görülür"},
            ],
            "canvas_code": """function drawLab(ctx, W, step) {
var H=400;
ctx.fillStyle='#e8eaf6';ctx.fillRect(0,0,W,H);
var titles=['1. Kesit Alma','2. Lama Yerlestirme','3. Boyama','4. Mikroskop Gozlemi'];
ctx.fillStyle='#1a237e';ctx.font='bold 18px sans-serif';ctx.fillText(titles[step]||'',W/2-80,25);
if(step===0){
  ctx.fillStyle='#f9a825';
  ctx.beginPath();ctx.ellipse(200,200,60,40,0,0,Math.PI*2);ctx.fill();
  ctx.strokeStyle='#f57f17';ctx.lineWidth=1;
  for(var i=0;i<4;i++){ctx.beginPath();ctx.ellipse(200,200,60-i*12,40-i*8,0,0,Math.PI*2);ctx.stroke();}
  ctx.fillStyle='#333';ctx.font='14px sans-serif';ctx.fillText('Sogan',180,265);
  ctx.fillStyle='#bdbdbd';ctx.fillRect(280,180,50,4);
  ctx.fillStyle='#795548';ctx.fillRect(325,174,20,16);
  ctx.fillStyle='#333';ctx.font='13px sans-serif';ctx.fillText('Ince kesit alin',400,200);
} else if(step===1){
  ctx.fillStyle='rgba(200,220,255,0.6)';ctx.fillRect(250,220,200,10);
  ctx.fillStyle='#333';ctx.font='13px sans-serif';ctx.fillText('Lam',335,218);
  ctx.fillStyle='rgba(249,168,37,0.3)';ctx.fillRect(300,218,100,6);
  ctx.fillStyle='#333';ctx.fillText('Kesit',335,215);
  ctx.fillStyle='rgba(66,165,245,0.5)';
  ctx.beginPath();ctx.arc(350,222,10,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#333';ctx.fillText('Su damlasi',400,230);
} else if(step===2){
  ctx.fillStyle='rgba(200,220,255,0.6)';ctx.fillRect(250,220,200,10);
  ctx.fillStyle='rgba(21,101,192,0.3)';ctx.fillRect(300,218,100,6);
  ctx.fillStyle='#1565c0';
  ctx.beginPath();ctx.arc(350,200,7,0,Math.PI*2);ctx.fill();
  ctx.beginPath();ctx.moveTo(350,193);ctx.lineTo(346,183);ctx.lineTo(354,183);ctx.closePath();ctx.fill();
  ctx.fillStyle='#333';ctx.font='13px sans-serif';ctx.fillText('Metilen Mavisi',290,175);
  ctx.fillStyle='rgba(200,220,255,0.4)';ctx.fillRect(290,230,120,8);
  ctx.fillStyle='#333';ctx.fillText('Lamel',335,250);
} else if(step===3){
  var cx=380,cy=200,r=100;
  ctx.strokeStyle='#1565c0';ctx.lineWidth=3;
  ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.stroke();
  ctx.fillStyle='#e3f2fd';
  ctx.beginPath();ctx.arc(cx,cy,r-2,0,Math.PI*2);ctx.fill();
  for(var row=0;row<4;row++){
    for(var col=0;col<5;col++){
      var hx=cx-55+col*28;
      var hy=cy-45+row*28;
      ctx.strokeStyle='#2e7d32';ctx.lineWidth=2;
      ctx.strokeRect(hx-11,hy-11,22,22);
      ctx.fillStyle='rgba(144,202,249,0.4)';
      ctx.fillRect(hx-10,hy-10,20,20);
      ctx.fillStyle='#1565c0';
      ctx.beginPath();ctx.arc(hx,hy,4,0,Math.PI*2);ctx.fill();
    }
  }
  ctx.fillStyle='#333';ctx.font='12px sans-serif';
  ctx.fillText('Hucre Duvari',500,160);
  ctx.fillText('Cekirdek (mavi)',500,185);
  ctx.fillText('Sitoplazma',500,210);
  ctx.fillStyle='#37474f';ctx.fillRect(100,80,60,220);
  ctx.fillStyle='#455a64';ctx.fillRect(80,270,100,25);
  ctx.fillStyle='#333';ctx.font='13px sans-serif';ctx.fillText('Mikroskop',85,315);
  ctx.fillText('40x Buyutme',85,335);
}
}""",
            "result": {
                "what_happened": "Soğan zarı hücreleri mikroskop altında gözlemlendi. Hücre duvarı, çekirdek ve sitoplazma ayırt edildi.",
                "why": "Metilen mavisi DNA'ya bağlanarak çekirdeği boyar ve görünür kılar. Bitki hücreleri düzgün dikdörtgen şeklindedir çünkü hücre duvarı vardır.",
                "formula": "",
                "real_life": "Tıbbi teşhiste kanser hücrelerinin tespiti, gıda kalite kontrolü, adli tıp incelemeleri"
            },
            "chemical_reaction": {"has_reaction": False, "equation": "", "type": ""},
        }

    def _physics_fallback(self):
        return {
            "title": "Eğik Düzlemde Hareket Deneyi",
            "subject": "fizik",
            "topic": "Kuvvet ve Hareket",
            "description": "Cismin eğik düzlemde yerçekimi etkisiyle hareketinin incelenmesi",
            "materials": [
                {"name": "Eğik düzlem", "icon": "📐", "quantity": "1 adet"},
                {"name": "Küçük araba/cisim", "icon": "🚗", "quantity": "1 adet"},
                {"name": "Kronometre", "icon": "⏱️", "quantity": "1 adet"},
                {"name": "Cetvel", "icon": "📏", "quantity": "1 adet"},
            ],
            "safety": [{"warning": "Cismin düşme yönünde durmayın.", "icon": "⚠️"}],
            "total_steps": 4,
            "steps": [
                {"step": 0, "title": "Düzenek Kurulumu", "description": "Eğik düzlemi 30° açıyla yerleştirin.", "observation": "Düzlem sabit"},
                {"step": 1, "title": "Cismi Yerleştirme", "description": "Cismi eğik düzlemin tepesine koyun.", "observation": "Cisim duruyor"},
                {"step": 2, "title": "Serbest Bırakma", "description": "Cismi serbest bırakın ve kronometreyi başlatın.", "observation": "Cisim hızlanarak kayar"},
                {"step": 3, "title": "Ölçüm ve Hesaplama", "description": "Varış süresini ve mesafeyi kaydedin.", "observation": "a = g·sin(30°) = 4.9 m/s²"},
            ],
            "canvas_code": """function drawLab(ctx, W, step) {
var H=400;
ctx.fillStyle='#e8eaf6';ctx.fillRect(0,0,W,H);
ctx.fillStyle='#8d6e63';ctx.fillRect(0,340,W,60);
var titles=['1. Duzenek Kurulumu','2. Cismi Yerlestirme','3. Serbest Birakma','4. Olcum ve Hesaplama'];
ctx.fillStyle='#1a237e';ctx.font='bold 18px sans-serif';ctx.fillText(titles[step]||'',W/2-100,25);
ctx.fillStyle='#b0bec5';ctx.strokeStyle='#78909c';ctx.lineWidth=3;
ctx.beginPath();ctx.moveTo(100,340);ctx.lineTo(550,340);ctx.lineTo(550,140);ctx.closePath();ctx.fill();ctx.stroke();
ctx.strokeStyle='#e53935';ctx.lineWidth=2;
ctx.beginPath();ctx.arc(550,340,50,-Math.PI,-Math.PI-0.524,true);ctx.stroke();
ctx.fillStyle='#e53935';ctx.font='bold 16px sans-serif';ctx.fillText('30',560,320);
if(step===0){
  ctx.fillStyle='#333';ctx.font='14px sans-serif';
  ctx.fillText('Egik duzlem 30 aci ile yerlestiriliyor',200,380);
  ctx.strokeStyle='#ff9800';ctx.lineWidth=2;ctx.setLineDash([5,5]);
  ctx.beginPath();ctx.moveTo(100,340);ctx.lineTo(550,340);ctx.stroke();ctx.setLineDash([]);
  ctx.fillText('Mesafe olculuyor...',200,360);
} else if(step===1){
  ctx.fillStyle='#1e88e5';ctx.fillRect(510,115,30,20);
  ctx.fillStyle='#1565c0';ctx.fillRect(515,100,20,18);
  ctx.fillStyle='#333';ctx.beginPath();ctx.arc(513,138,5,0,Math.PI*2);ctx.fill();
  ctx.beginPath();ctx.arc(537,138,5,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#333';ctx.font='14px sans-serif';ctx.fillText('Cisim tepede hazir',350,100);
} else if(step===2){
  ctx.fillStyle='#1e88e5';ctx.fillRect(320,225,30,20);
  ctx.fillStyle='#1565c0';ctx.fillRect(325,210,20,18);
  ctx.fillStyle='#333';ctx.beginPath();ctx.arc(323,248,5,0,Math.PI*2);ctx.fill();
  ctx.beginPath();ctx.arc(347,248,5,0,Math.PI*2);ctx.fill();
  ctx.strokeStyle='#e53935';ctx.lineWidth=3;
  ctx.beginPath();ctx.moveTo(335,245);ctx.lineTo(335,295);ctx.stroke();
  ctx.fillStyle='#e53935';ctx.beginPath();ctx.moveTo(329,290);ctx.lineTo(341,290);ctx.lineTo(335,300);ctx.closePath();ctx.fill();
  ctx.fillStyle='#e53935';ctx.font='13px sans-serif';ctx.fillText('mg',342,285);
  ctx.strokeStyle='#4caf50';ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(335,245);ctx.lineTo(290,270);ctx.stroke();
  ctx.fillStyle='#4caf50';ctx.font='12px sans-serif';ctx.fillText('mg sin(30)',240,290);
  ctx.fillStyle='#fff';ctx.strokeStyle='#333';ctx.lineWidth=2;
  ctx.beginPath();ctx.arc(680,80,35,0,Math.PI*2);ctx.fill();ctx.stroke();
  ctx.fillStyle='#333';ctx.font='bold 14px sans-serif';ctx.fillText('1.2s',662,85);
} else if(step===3){
  ctx.fillStyle='#1e88e5';ctx.fillRect(130,310,30,20);
  ctx.fillStyle='#1565c0';ctx.fillRect(135,295,20,18);
  ctx.fillStyle='#333';ctx.beginPath();ctx.arc(133,333,5,0,Math.PI*2);ctx.fill();
  ctx.beginPath();ctx.arc(157,333,5,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#fff';ctx.strokeStyle='#333';ctx.lineWidth=2;
  ctx.beginPath();ctx.arc(680,80,35,0,Math.PI*2);ctx.fill();ctx.stroke();
  ctx.fillStyle='#333';ctx.font='bold 14px sans-serif';ctx.fillText('2.3s',662,85);
  ctx.fillStyle='#1a237e';ctx.font='bold 16px sans-serif';
  ctx.fillText('a = g sin(30) = 9.8 x 0.5 = 4.9 m/s2',180,390);
  ctx.fillStyle='#4caf50';ctx.font='bold 18px sans-serif';ctx.fillText('Olcum Tamamlandi',280,60);
}
}""",
            "result": {
                "what_happened": "Cisim eğik düzlemde hızlanarak kaydı. Süre ve mesafe ölçüldü.",
                "why": "Yerçekimi kuvvetinin eğik düzleme paralel bileşeni (mg·sinθ) cismi hızlandırır. Açı arttıkça ivme artar.",
                "formula": "a = g·sin(θ) = 9.8 × sin(30°) = 4.9 m/s²",
                "real_life": "Kayak pistleri, kaydıraklar, rampa tasarımı, araç frenleme mesafesi hesabı"
            },
            "chemical_reaction": {"has_reaction": False, "equation": "", "type": ""},
        }
