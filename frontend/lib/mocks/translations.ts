import type { EmergencyReport, Language } from "../../types/index.ts";
import { ServiceError } from "../services/contracts.ts";
const canonical: Record<Language, string> = {
  en: "Water entering Krishna Apartments Block C. My grandmother cannot walk.",
  hi: "कृष्णा अपार्टमेंट्स ब्लॉक C में पानी घुस रहा है। मेरी दादी चल नहीं सकतीं।",
  kn: "ಕೃಷ್ಣ ಅಪಾರ್ಟ್‌ಮೆಂಟ್ಸ್ ಬ್ಲಾಕ್ C ಒಳಗೆ ನೀರು ಬರುತ್ತಿದೆ. ನನ್ನ ಅಜ್ಜಿಗೆ ನಡೆಯಲು ಸಾಧ್ಯವಿಲ್ಲ.",
  ta: "கிருஷ்ணா அடுக்குமாடி குடியிருப்பு பிளாக் C-க்குள் தண்ணீர் வருகிறது. என் பாட்டியால் நடக்க முடியாது.",
  te: "కృష్ణ అపార్ట్‌మెంట్స్ బ్లాక్ C లోకి నీరు వస్తోంది. మా అమ్మమ్మ నడవలేరు.",
  ml: "കൃഷ്ണ അപ്പാർട്ട്മെന്റ്സ് ബ്ലോക്ക് C-യിൽ വെള്ളം കയറുന്നു. എന്റെ മുത്തശ്ശിക്ക് നടക്കാൻ കഴിയില്ല.",
  mr: "कृष्णा अपार्टमेंट्स ब्लॉक C मध्ये पाणी शिरत आहे. माझी आजी चालू शकत नाही.",
  bn: "কৃষ্ণা অ্যাপার্টমেন্টস ব্লক C-তে জল ঢুকছে। আমার ঠাকুমা হাঁটতে পারেন না।",
  gu: "કૃષ્ણા એપાર્ટમેન્ટ્સ બ્લોક C માં પાણી આવી રહ્યું છે. મારી દાદી ચાલી શકતાં નથી.",
  pa: "ਕ੍ਰਿਸ਼ਨਾ ਅਪਾਰਟਮੈਂਟਸ ਬਲਾਕ C ਵਿੱਚ ਪਾਣੀ ਆ ਰਿਹਾ ਹੈ। ਮੇਰੀ ਦਾਦੀ ਤੁਰ ਨਹੀਂ ਸਕਦੀ।",
  ur: "کرشنا اپارٹمنٹس بلاک C میں پانی داخل ہو رہا ہے۔ میری دادی چل نہیں سکتیں۔",
  as: "কৃষ্ণা এপাৰ্টমেণ্টছ ব্লক C-ত পানী সোমাইছে। মোৰ আইতাই খোজ কাঢ়িব নোৱাৰে।",
  or: "କୃଷ୍ଣା ଆପାର୍ଟମେଣ୍ଟସ୍ ବ୍ଲକ୍ C ଭିତରକୁ ପାଣି ପଶୁଛି। ମୋ ଜେଜେମା ଚାଲି ପାରୁନାହାନ୍ତି।",
};
export async function translateMockReport(report: EmergencyReport, language: Language): Promise<EmergencyReport> {
  // Only known fixtures are translated. Never claim to translate arbitrary text.
  let translation: string | undefined;
  if (report.originalLanguage === language) translation = report.originalText;
  else if (report.originalText === canonical.en) translation = canonical[language];
  else if (report.translatedLanguage === language) translation = report.translatedText;
  if (!translation) throw new ServiceError("error.translation");
  return { ...report, translatedText: translation, translatedLanguage: language };
}
