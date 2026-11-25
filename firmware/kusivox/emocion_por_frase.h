// KusiVox: elige la animacion del personaje segun las palabras de cada frase.
//
// El servicio en la nube manda una sola emocion por respuesta. Para que el personaje
// reaccione mientras habla, el firmware revisa cada frase que va a decir (mensaje
// "tts" con estado "sentence_start") y, si encuentra una palabra o un emoji con carga
// emocional, cambia la animacion. Si la frase no tiene ninguna, deja la anterior.
//
// La busqueda ignora mayusculas, tildes y signos de puntuacion. Una clave que empieza
// con espacio debe estar al inicio de una palabra; si termina con espacio, la palabra
// debe terminar ahi. Gana la clave que aparece primero en la frase (y, si empiezan en
// el mismo lugar, la mas larga).
#pragma once

#include <cctype>
#include <cstring>
#include <string>

namespace kusivox {

inline std::string NormalizarFrase(const char* texto) {
    std::string s = " ";
    const unsigned char* c = reinterpret_cast<const unsigned char*>(texto);
    while (*c) {
        if (c[0] == 0xC3 && c[1]) {  // letras con tilde y la enie (UTF-8 de 2 bytes)
            char r = 0;
            switch (c[1]) {
                case 0xA1: case 0x81: case 0xA0: case 0x80: r = 'a'; break;
                case 0xA9: case 0x89: case 0xA8: case 0x88: r = 'e'; break;
                case 0xAD: case 0x8D: case 0xAC: case 0x8C: r = 'i'; break;
                case 0xB3: case 0x93: case 0xB2: case 0x92: r = 'o'; break;
                case 0xBA: case 0x9A: case 0xBC: case 0x9C: case 0xB9: case 0x99: r = 'u'; break;
                case 0xB1: case 0x91: r = 'n'; break;
            }
            if (r) {
                s += r;
                c += 2;
                continue;
            }
        }
        if (c[0] == 0xC2 && c[1]) {  // signos de apertura y comillas latinas
            s += ' ';
            c += 2;
            continue;
        }
        if (c[0] == 0xE2 && c[1] == 0x80 && c[2]) {  // puntos suspensivos, rayas y comillas
            s += ' ';
            c += 3;
            continue;
        }
        if (c[0] < 0x80) {
            s += std::isalnum(c[0]) ? static_cast<char>(std::tolower(c[0])) : ' ';
        } else {
            s += static_cast<char>(c[0]);  // emojis: se conservan para compararlos tal cual
        }
        ++c;
    }
    s += ' ';
    return s;
}

struct ReglaEmocion {
    const char* clave;
    const char* emocion;
};

inline const char* EmocionDeFrase(const char* texto) {
    static const ReglaEmocion kReglas[] = {
        // risa
        {"\xF0\x9F\x98\x82", "laughing"}, {"\xF0\x9F\xA4\xA3", "laughing"},
        {" jaja", "laughing"}, {" jeje", "laughing"}, {" jiji", "laughing"}, {" jojo", "laughing"},
        // alegria
        {"\xF0\x9F\x98\x8A", "happy"}, {"\xF0\x9F\x98\x84", "happy"}, {"\xF0\x9F\x98\x81", "happy"},
        {"\xF0\x9F\x99\x82", "happy"}, {"\xF0\x9F\xA5\xB3", "happy"},
        {" genial", "happy"}, {" feliz", "happy"}, {" excelente", "happy"}, {" perfecto", "happy"},
        {" que bueno", "happy"}, {" me alegra", "happy"}, {" felicidades", "happy"}, {" bien hecho", "happy"},
        {" listo ", "happy"}, {" hurra", "happy"}, {" estupendo", "happy"}, {" fantastic", "happy"},
        {" maravillos", "happy"}, {" buenos dias", "happy"}, {" hola ", "happy"},
        // diversion
        {" divertid", "funny"}, {" gracios", "funny"}, {" chistos", "funny"}, {" que risa", "funny"},
        // carino
        {"\xE2\x9D\xA4", "loving"}, {"\xF0\x9F\x98\x8D", "loving"}, {"\xF0\x9F\xA5\xB0", "loving"},
        {" te quiero", "loving"}, {" amor ", "loving"}, {" carino", "loving"}, {" corazon", "loving"},
        {" adoro", "loving"},
        // tristeza y llanto
        {"\xF0\x9F\x98\xA2", "sad"}, {"\xF0\x9F\x98\x94", "sad"},
        {" lo siento", "sad"}, {" lamento", "sad"}, {" triste", "sad"}, {" que pena", "sad"},
        {" lastima", "sad"}, {" lamentablemente", "sad"}, {" por desgracia", "sad"},
        {"\xF0\x9F\x98\xAD", "crying"}, {" llorar", "crying"}, {" lloro", "crying"}, {" llorando", "crying"},
        // enojo
        {"\xF0\x9F\x98\xA0", "angry"}, {"\xF0\x9F\x98\xA1", "angry"},
        {" enojad", "angry"}, {" molest", "angry"}, {" furios", "angry"}, {" rabia", "angry"},
        // sorpresa y susto
        {"\xF0\x9F\x98\xAE", "surprised"}, {"\xF0\x9F\x98\xAF", "surprised"}, {"\xF0\x9F\x98\xB2", "surprised"},
        {" wow", "surprised"}, {" guau", "surprised"}, {" increible", "surprised"}, {" sorprend", "surprised"},
        {" en serio", "surprised"}, {" vaya", "surprised"}, {" oh ", "surprised"}, {" atencion", "surprised"},
        {"\xF0\x9F\x98\xB1", "shocked"}, {" no puede ser", "shocked"}, {" que miedo", "shocked"},
        {" cuidado", "shocked"}, {" peligro", "shocked"},
        // pensar y dudar
        {"\xF0\x9F\xA4\x94", "thinking"}, {" hmm", "thinking"}, {" mmm", "thinking"},
        {" dejame pensar", "thinking"}, {" veamos", "thinking"}, {" a ver ", "thinking"},
        {" creo que", "thinking"}, {" quiza", "thinking"}, {" tal vez", "thinking"}, {" buscando", "thinking"},
        {" seguro que quieres", "thinking"},
        {"\xF0\x9F\x98\x95", "confused"}, {" no entiendo", "confused"}, {" no entendi", "confused"},
        {" no estoy seguro", "confused"}, {" no se ", "confused"}, {" confundid", "confused"},
        // complicidad y estilo
        {"\xF0\x9F\x98\x89", "winking"}, {" secreto", "winking"}, {" entre nos", "winking"},
        {"\xF0\x9F\x98\x8E", "cool"}, {" facil", "cool"}, {" sin problema", "cool"}, {" pan comido", "cool"},
        {" chevere", "cool"},
        {"\xF0\x9F\x98\x8C", "relaxed"}, {" tranquil", "relaxed"}, {" relaj", "relaxed"}, {" calma", "relaxed"},
        {" respira", "relaxed"},
        {"\xF0\x9F\x98\x8B", "delicious"}, {" delicios", "delicious"}, {" rico ", "delicious"},
        {" rica ", "delicious"}, {" comida", "delicious"}, {" hambre", "delicious"},
        {"\xF0\x9F\x98\x98", "kissy"}, {" beso", "kissy"},
        {" por supuesto", "confident"}, {" claro ", "confident"}, {" sin duda", "confident"},
        {" yo puedo", "confident"}, {" enseguida", "confident"}, {" ahora mismo", "confident"},
        {" ya lo hago", "confident"},
        {"\xF0\x9F\x98\xB4", "sleepy"}, {" sueno", "sleepy"}, {" dormir", "sleepy"},
        {" buenas noches", "sleepy"}, {" cansad", "sleepy"},
        {"\xF0\x9F\x98\x9C", "silly"}, {"\xF0\x9F\xA4\xAA", "silly"}, {" broma", "silly"},
        {" tonteria", "silly"}, {" travies", "silly"},
        {"\xF0\x9F\x98\xB3", "embarrassed"}, {" perdon", "embarrassed"}, {" disculpa", "embarrassed"},
        {" verguenza", "embarrassed"}, {" uy ", "embarrassed"}, {" ups ", "embarrassed"},
    };
    if (texto == nullptr || *texto == '\0') {
        return nullptr;
    }
    const std::string frase = NormalizarFrase(texto);
    size_t mejor = std::string::npos;
    size_t largo = 0;
    const char* emocion = nullptr;
    for (const auto& regla : kReglas) {
        const size_t pos = frase.find(regla.clave);
        if (pos == std::string::npos) {
            continue;
        }
        const size_t l = std::strlen(regla.clave);
        if (pos < mejor || (pos == mejor && l > largo)) {
            mejor = pos;
            largo = l;
            emocion = regla.emocion;
        }
    }
    return emocion;
}

}  // namespace kusivox
