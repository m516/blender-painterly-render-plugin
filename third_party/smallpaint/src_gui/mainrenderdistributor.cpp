#include "mainwindow.h"
#include <thread>
#include "main.h"
#include "sceneGeometries.h"
#include "renderfunctions.h"

bool rendering = false;
std::string currentRenderer;
MainWindow* win;
int currentID;
int spp;
int id = 0;
std::vector<bool> running;

void setInstanceForRenderDistribution(MainWindow* w) {
	win = w;
}

void setRendering(bool r) {
	rendering = r;
}

bool isRendering() {
	return rendering;
}

void cancelRendering() {
	running.at(currentID) = false;
}

namespace smallpaint_fixed {

void imageOutput(smallpaint_fixed::Vec **pix, int s) {
	emit win->smallpaint_fixedSignal(pix, s);
}

void processImage(smallpaint_fixed::Vec **pix, int s) {
	s++;
	std::string name = currentRenderer + "_" + to_string(s) + "_spp.ppm";

    QImage image(win->width, win->height, QImage::Format_RGB32);

	for (int row = 0; row < win->height; row++) {
		for (int col = 0; col < win->width; col++) {
            image.setPixel(col, row, qRgb(min((int)pix[col][row].x / s, 255), min((int)pix[col][row].y / s, 255), min((int)pix[col][row].z / s, 255)));
		}
	}
    win->drawImage(image, name, s, spp);
	if (spp == s) {
		rendering = false;
		emit win->on_renderButton_clicked();
	}
}

}

namespace smallpaint_painterly {

void imageOutput(smallpaint_painterly::Vec **pix, int s) {
	emit win->smallpaint_painterlySignal(pix, s);
}

void processImage(smallpaint_painterly::Vec **pix, int s) {
	s++;
	std::string name = currentRenderer + "_" + to_string(s) + "_spp.ppm";

    QImage image(win->width, win->height, QImage::Format_RGB32);

	for (int row = 0; row < win->height; row++) {
		for (int col = 0; col < win->width; col++) {
            image.setPixel(col, row, qRgb(min((int)pix[col][row].x / s, 255), min((int)pix[col][row].y / s, 255), min((int)pix[col][row].z / s, 255)));
		}
	}
    win->drawImage(image, name, s, spp);
	if (spp == s) {
		rendering = false;
		emit win->on_renderButton_clicked();
	}
}
}

namespace smallpaint_bvh {

void imageOutput(smallpaint_bvh::Vec **pix, int s) {
	emit win->smallpaint_bvhSignal(pix, s);
}

void processImage(smallpaint_bvh::Vec **pix, int s) {
	s++;
	std::string name = currentRenderer + "_" + to_string(s) + "_spp.ppm";

    QImage image(win->width, win->height, QImage::Format_RGB32);

	for (int row = 0; row < win->height; row++) {
		for (int col = 0; col < win->width; col++) {
            image.setPixel(col, row, qRgb(min((int)pix[col][row].x / s, 255), min((int)pix[col][row].y / s, 255), min((int)pix[col][row].z / s, 255)));
		}
	}
    win->drawImage(image, name, s, spp);
	if (spp == s) {
		rendering = false;
		emit win->on_renderButton_clicked();
	}
}

}

namespace smallpaint_pssmlt {

void imageOutput(smallpaint_pssmlt::Vec **pix, int s) {
	emit win->smallpaint_pssmltSignal(pix, s);
}

void processImage(smallpaint_pssmlt::Vec **pix, int s) {
	s++;
	std::string name = currentRenderer + "_" + to_string(s) + "_spp.ppm";

    QImage image(win->width, win->height, QImage::Format_RGB32);

	for (int row = 0; row < win->height; row++) {
		for (int col = 0; col < win->width; col++) {
            image.setPixel(col, row, qRgb(min((int)pix[col][row].x, 255), min((int)pix[col][row].y, 255), min((int)pix[col][row].z, 255)));
		}
	}

    win->drawImage(image, name, s, spp);
	if (spp == s) {
		rendering = false;
		emit win->on_renderButton_clicked();
	}
}

}

namespace smallpaint_smallmedia {

void imageOutput(smallpaint_smallmedia::Vec **pix, int s) {
	emit win->smallpaint_smallmediaSignal(pix, s);
}

int colorToInt(double clr, bool gammacorrection = false) {
	if (gammacorrection) clr = pow(clr, 1.0 / 2.2);
	int converted = (int)(clr * 255 + 0.5);
	return converted < 0 ? 0 : converted > 255 ? 255 : converted;
}

void processImage(smallpaint_smallmedia::Vec **pix, int s) {
	s++;
	std::string name = currentRenderer + "_" + to_string(s) + "_spp.ppm";

    QImage image(win->width, win->height, QImage::Format_RGB32);

	for (int row = 0; row < win->height; row++) {
		for (int col = 0; col < win->width; col++) {
            image.setPixel(col, row, qRgb(colorToInt(pix[col][row].x / s, false), colorToInt(pix[col][row].y / s, false), colorToInt(pix[col][row].z / s, false)));
		}
	}

    win->drawImage(image, name, s, spp);
	if (spp == s) {
		rendering = false;
		emit win->on_renderButton_clicked();
	}
}

}

namespace smallpaint_ppm {

void imageOutput(smallpaint_ppm::Vec **pix, int s) {

	emit win->smallpaint_ppmSignal(pix, s);
}

int toInt(double x) {
	return int(pow(1 - exp(-x), 1 / 2.2) * 255 + .5);
}

void processImage(smallpaint_ppm::Vec **pix, int s) {
	s++;
	std::string name = currentRenderer + "_" + to_string(s) + "_photons.ppm";

    QImage image(win->width, win->height, QImage::Format_RGB32);

	for (int col = 0; col < win->width; col++) {
		for (int row = 0; row < win->height; row++) {
            image.setPixel(col, row, qRgb(toInt(pix[col][row].x), toInt(pix[col][row].y), toInt(pix[col][row].z)));
		}
	}
    win->drawImage(image, name, s, spp);
	if (spp == s) {
		rendering = false;
		emit win->on_renderButton_clicked();
	}
}

}

namespace smallpaint_vrl {

void imageOutput(smallpaint_vrl::Vec **pix, int s) {

    emit win->smallpaint_vrlSignal(pix, s);
}

int toInt(double x) {
    return min((int)(x * 255.0), 255);
}

void processImage(smallpaint_vrl::Vec **pix, int s) {
    s++;
    std::string name = currentRenderer + "_" + to_string(s) + "_spp.ppm";

    QImage image(win->width, win->height, QImage::Format_RGB32);

    for (int col = 0; col < win->width; col++) {
        for (int row = 0; row < win->height; row++) {
            image.setPixel(col, row, qRgb(toInt(pix[col][row].x / (float)s), toInt(pix[col][row].y / (float)s), toInt(pix[col][row].z / (float)s)));
        }
    }
    win->drawImage(image, name, s, spp);
    if (spp == s) {
        rendering = false;
        emit win->on_renderButton_clicked();
    }
}

}

namespace smallpaint {

void sendToRender(RenderInfo info, std::string renderer) {
	if (!rendering) {
        spp = info.spp;
		rendering = true;
		currentID = id;
		running.push_back(true);
		currentRenderer = renderer;
		if (renderer == "smallpaint_fixed") {
            std::thread t(smallpaint_fixed::render, id, info.size, info.spp, info.refr);
			t.detach();
		}
		if (renderer == "smallpaint_painterly") {
            std::thread t(smallpaint_painterly::render, id, info.size, info.spp, info.refr);
			t.detach();
		}
		if (renderer == "smallpaint_bvh") {
            std::thread t(smallpaint_bvh::render, id, info.size, info.spp, info.refr);
			t.detach();
		}
		if (renderer == "smallpaint_pssmlt") {
            std::thread t(smallpaint_pssmlt::render, id, info.size, info.spp, info.refr);
			t.detach();
		}
		if (renderer == "smallpaint_smallmedia") {
            std::thread t(smallpaint_smallmedia::render, id, info.size, info.spp, info.refr);
			t.detach();
		}
		if (renderer == "smallpaint_ppm") {
            std::thread t(smallpaint_ppm::render, id, info.size, info.spp, info.refr);
			t.detach();
		}
        if (renderer == "smallpaint_vrl") {
            std::thread t(smallpaint_vrl::render, id, info.size, info.spp,  info.vrlps, info.scene, info.bounces, info.sigma_a, info.sigma_s, info.g, info.sampling, info.refr, info.intensity, info.mediumRadiance, info.surfaceRadiance);
            t.detach();
        }
		id++;
	}
}

bool isRunning(int id) {
	return running.at(id);
}

}
