#pragma once

void setRendering(bool rendering);
bool isRendering();
void cancelRendering();

namespace smallpaint_fixed {
struct Vec;
void imageOutput(Vec **pix, int spp);
void processImage(Vec **pix, int spp);
}
namespace smallpaint_painterly {
struct Vec;
void imageOutput(Vec **pix, int spp);
void processImage(Vec **pix, int spp);
}
namespace smallpaint_bvh {
struct Vec;
void imageOutput(Vec **pix, int spp);
void processImage(Vec **pix, int spp);
}
namespace smallpaint_pssmlt {
struct Vec;
void imageOutput(Vec **pix, int spp);
void processImage(Vec **pix, int spp);
}
namespace smallpaint_smallmedia {
struct Vec;
void imageOutput(Vec **pix, int spp);
void processImage(Vec **pix, int spp);
}
namespace smallpaint_ppm {
struct Vec;
void imageOutput(Vec **pix, int spp);
void processImage(Vec **pix, int spp);
}
namespace smallpaint_vrl {
struct Vec;
void imageOutput(Vec **pix, int spp);
void processImage(Vec **pix, int spp);
}
namespace smallpaint {

struct RenderInfo {
  int size = 512, spp = 50, vrlps = 10, bounces = 1, scene = 0, sampling = 4, intensity = 1000;
  double refr = 1.5, sigma_a = 0.1, sigma_s = 0.01, g = 0.0;
  bool mediumRadiance = true, surfaceRadiance = true;
};

bool isRunning(int id);
void sendToRender(RenderInfo info, std::string renderer);
}
