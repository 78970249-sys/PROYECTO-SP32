// Mascotas de KusiVox: perrito, gatito, conejito, osito panda y pajarito, cada uno en 3 colores.
//
// - Las animaciones se llaman <animal>_<emocion>.gif (por ejemplo gato_happy) y vienen en la
//   zona de recursos (assets). Cada animal tiene 12 emociones; las otras 9 del firmware usan
//   la mas parecida (EmocionDisponible).
// - El color se cambia sin guardar copias: los GIF usan una paleta global de 64 colores cuyas
//   entradas 0-31 son el pelaje. Al abrir un GIF con la marca de KusiVox en la entrada 63,
//   AplicarColorMascota reemplaza esas 32 entradas por las del color elegido.
// - La mascota y el color se guardan en la memoria NVS (espacio "kusivox") y se cambian por voz
//   con la herramienta self.mascota.cambiar.
#pragma once

#include <atomic>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

#include "paletas_mascotas.h"
#include "settings.h"

namespace kusivox {

struct AnimalMascota {
    const char* clave;      // prefijo de los archivos
    const char* nombre;     // como se dice
    const char* palabras[8];
};

static const AnimalMascota kAnimalesMascota[] = {
    {"perro", "perrito", {"perr", "shih tzu", "shitzu", "cachorr", "can ", nullptr}},
    {"gato", "gatito", {"gat", "michi", "minin", "felino", nullptr}},
    {"conejo", "conejito", {"conej", nullptr}},
    {"panda", "osito panda", {"panda", "oso", "osit", nullptr}},
    {"pajaro", "pajarito", {"pajar", "ave", "canari", "pollit", "pajaril", nullptr}},
};
static const int kNumAnimales = sizeof(kAnimalesMascota) / sizeof(kAnimalesMascota[0]);

// Minusculas sin tildes, con espacios en los extremos: " cambia a color cafe ".
inline std::string NormalizarMascota(const std::string& texto) {
    std::string r = " ";
    for (size_t i = 0; i < texto.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(texto[i]);
        if (c == 0xC3 && i + 1 < texto.size()) {
            unsigned char d = static_cast<unsigned char>(texto[++i]) | 0x20;  // mayuscula -> minuscula
            char base = 0;
            if (d >= 0xA0 && d <= 0xA5) base = 'a';
            else if (d >= 0xA8 && d <= 0xAB) base = 'e';
            else if (d >= 0xAC && d <= 0xAF) base = 'i';
            else if (d >= 0xB2 && d <= 0xB6) base = 'o';
            else if (d >= 0xB9 && d <= 0xBC) base = 'u';
            else if (d == 0xB1) base = 'n';
            r += base ? base : ' ';
        } else if (c < 0x80 && std::isalnum(c)) {
            r += static_cast<char>(std::tolower(c));
        } else {
            r += ' ';
        }
    }
    return r + " ";
}

struct EstadoMascota {
    std::atomic<int> animal{0};
    std::atomic<int> color{0};
};

inline EstadoMascota& Mascota() {
    static EstadoMascota estado;
    static bool cargado = [] {
        Settings ajustes("kusivox", false);
        std::string guardado = ajustes.GetString("mascota", "perro");
        for (int i = 0; i < kNumAnimales; ++i) {
            if (guardado == kAnimalesMascota[i].clave) estado.animal = i;
        }
        int color = ajustes.GetInt("color", 0);
        estado.color = (color >= 0 && color < 3) ? color : 0;
        return true;
    }();
    (void)cargado;
    return estado;
}

// Las 12 emociones dibujadas; las demas usan la mas parecida. nullptr si no es una emocion.
inline const char* EmocionDisponible(const char* emocion) {
    static const char* propias[] = {"neutral", "happy", "laughing", "sad", "crying", "angry",
                                    "surprised", "thinking", "sleepy", "loving", "confused", "winking"};
    for (const char* p : propias) {
        if (std::strcmp(emocion, p) == 0) return p;
    }
    static const char* parecidas[][2] = {
        {"funny", "laughing"}, {"silly", "laughing"}, {"shocked", "surprised"}, {"cool", "winking"},
        {"confident", "happy"}, {"relaxed", "neutral"}, {"delicious", "happy"}, {"kissy", "loving"},
        {"embarrassed", "confused"},
    };
    for (auto& par : parecidas) {
        if (std::strcmp(emocion, par[0]) == 0) return par[1];
    }
    return nullptr;
}

// "happy" -> "gato_happy" segun la mascota elegida. false si no hay animacion para esa emocion.
inline bool NombreConMascota(const char* emocion, char* salida, size_t tam) {
    const char* propia = emocion ? EmocionDisponible(emocion) : nullptr;
    if (!propia) return false;
    std::snprintf(salida, tam, "%s_%s", kAnimalesMascota[Mascota().animal.load()].clave, propia);
    return true;
}

inline const PaletaMascota* PaletaActual() {
    const char* animal = kAnimalesMascota[Mascota().animal.load()].clave;
    int color = Mascota().color.load();
    for (const auto& p : kPaletasMascota) {
        if (std::strcmp(p.animal, animal) == 0 && p.indice == color) return &p;
    }
    return nullptr;
}

// Se llama al abrir cada GIF: solo cambia los GIF de mascota (paleta de 64 con la marca en la 63).
inline void AplicarColorMascota(uint8_t* colores, int tam) {
    if (tam != 64 || std::memcmp(colores + 63 * 3, kMarcaMascota, 3) != 0) return;
    const PaletaMascota* p = PaletaActual();
    if (p) std::memcpy(colores, p->rgb, sizeof(p->rgb));
}

// Cambia la mascota y/o el color a partir de lo que dijo la persona y lo guarda. Devuelve el texto
// para responder en voz.
inline std::string CambiarMascota(const std::string& animal_dicho, const std::string& color_dicho) {
    std::string animal_n = NormalizarMascota(animal_dicho);
    std::string color_n = NormalizarMascota(color_dicho);
    int animal = Mascota().animal.load();
    int color = Mascota().color.load();
    if (animal_n.find_first_not_of(' ') != std::string::npos) {
        int elegido = -1;
        for (int i = 0; i < kNumAnimales && elegido < 0; ++i) {
            for (int j = 0; kAnimalesMascota[i].palabras[j]; ++j) {
                if (animal_n.find(kAnimalesMascota[i].palabras[j]) != std::string::npos) {
                    elegido = i;
                    break;
                }
            }
        }
        if (elegido < 0) {
            return "No conozco ese animal. Puedo ser perrito, gatito, conejito, osito panda o pajarito.";
        }
        if (elegido != animal) color = 0;
        animal = elegido;
    }
    if (color_n.find_first_not_of(' ') != std::string::npos) {
        // sinonimos de colores
        const char* sinonimos[][2] = {{" marron ", " cafe "}, {" azul ", " celeste "}, {" amarill", " amarillo "},
                                      {" plomo ", " gris "}, {" anaranjado ", " naranja "}};
        for (auto& s : sinonimos) {
            if (color_n.find(s[0]) != std::string::npos) color_n += std::string(s[1]) + " ";
        }
        bool original = color_n.find(" original ") != std::string::npos || color_n.find(" normal ") != std::string::npos ||
                        color_n.find(" clasico ") != std::string::npos || color_n.find(" de siempre ") != std::string::npos;
        int elegido = original ? 0 : -1;
        // primero el color que empieza el nombre ("negro y blanco"), luego cualquiera de sus palabras
        for (int pasada = 0; pasada < 2 && elegido < 0; ++pasada) {
            for (const auto& p : kPaletasMascota) {
                if (std::strcmp(p.animal, kAnimalesMascota[animal].clave) != 0) continue;
                std::string nombre = NormalizarMascota(p.nombre);
                size_t inicio = 1, fin;
                bool coincide = false;
                int palabra = 0;
                while ((fin = nombre.find(' ', inicio)) != std::string::npos) {
                    std::string w = nombre.substr(inicio, fin - inicio);
                    if (!w.empty() && w != "y" && (pasada == 1 || palabra == 0) &&
                        color_n.find(" " + w + " ") != std::string::npos) {
                        coincide = true;
                    }
                    if (!w.empty()) ++palabra;
                    inicio = fin + 1;
                }
                if (coincide) {
                    elegido = p.indice;
                    break;
                }
            }
        }
        if (elegido < 0) {
            std::string lista;
            for (const auto& p : kPaletasMascota) {
                if (std::strcmp(p.animal, kAnimalesMascota[animal].clave) != 0) continue;
                lista += (lista.empty() ? "" : ", ") + std::string(p.nombre);
            }
            return std::string("Como ") + kAnimalesMascota[animal].nombre + " puedo ser de color " + lista + ".";
        }
        color = elegido;
    }
    Mascota().animal = animal;
    Mascota().color = color;
    {
        Settings ajustes("kusivox", true);
        ajustes.SetString("mascota", kAnimalesMascota[animal].clave);
        ajustes.SetInt("color", color);
    }
    const PaletaMascota* p = PaletaActual();
    return std::string("Listo, ahora soy un ") + kAnimalesMascota[animal].nombre + " de color " +
           (p ? p->nombre : "original") + ".";
}

}  // namespace kusivox
