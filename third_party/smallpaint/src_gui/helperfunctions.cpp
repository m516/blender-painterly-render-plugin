#include "helperfunctions.h"
#include "mainwindow.h"

MainWindow* mainWindow;

/**
 * Saves MainWindow instance.
 */
void setInstanceForHelperFunctions(MainWindow* w) {
	mainWindow = w;
}

/**
 * Saves image to specified path.
 */
void HelperFunctions::saveImage() {
    if (mainWindow->lastImage == "") return;
    //mainWindow->ui->renderedImage->clear();
    QString filename = QFileDialog::getSaveFileName(mainWindow, QObject::tr("Save Image"), QString::fromUtf8(mainWindow->lastImage.c_str()), QObject::tr("Image Files (*.ppm)"));
    if (filename == "") {
        mainWindow->ui->renderInfo->setText("Image not saved");
    } else {
		mainWindow->ui->renderInfo->setText("Image saved to: " + filename);
		mainWindow->image.save(filename, "PPM", -1);
    }
    mainWindow->resizeImage();
}

/**
 * Returns the renderer short name.
 */
QString HelperFunctions::getRenderer(QString renderer) {
	if (renderer == "Path Tracing (Fixed)") {
		return "fixed";
	}
	if (renderer == "Path Tracing (Painterly)") {
		return "painterly";
	}
	if (renderer == "Bounding Volume Hierarchy") {
		return "bvh";
	}
	if (renderer == "Primary Sample Space MLT") {
		return "pssmlt";
	}
	if (renderer == "Volumetric Path Tracing") {
		return "smallmedia";
	}
	if (renderer == "Progressive Photon Mapping") {
		return "ppm";
	}
    if (renderer == "Virtual Ray Lights") {
        return "vrl";
    }
	if (renderer == "Tests") {
		return "tests";
	}
	return "";
}

/**
 * Changes Menu items.
 */
void HelperFunctions::changedComboBox(QString renderer) {
	if (renderer == "fixed") {
		mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->fixed);
        if (mainWindow->ui->fixedSize->text() == "") mainWindow->ui->fixedSize->setText(QString::number(512));
        if (mainWindow->ui->fixedSamples->text() == "") mainWindow->ui->fixedSamples->setText(QString::number(50));
        if (mainWindow->ui->fixedRefraction->text() == "") mainWindow->ui->fixedRefraction->setText(QString::number(1.5));
	}
	if (renderer == "painterly") {
		mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->painterly);
        if (mainWindow->ui->painterlySize->text() == "") mainWindow->ui->painterlySize->setText(QString::number(512));
        if (mainWindow->ui->painterlySamples->text() == "") mainWindow->ui->painterlySamples->setText(QString::number(50));
        if (mainWindow->ui->painterlyRefraction->text() == "") mainWindow->ui->painterlyRefraction->setText(QString::number(1.5));
	}
	if (renderer == "bvh") {
		mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->bvh);
        if (mainWindow->ui->bvhSize->text() == "") mainWindow->ui->bvhSize->setText(QString::number(512));
        if (mainWindow->ui->bvhSamples->text() == "") mainWindow->ui->bvhSamples->setText(QString::number(50));
        if (mainWindow->ui->bvhRefraction->text() == "") mainWindow->ui->bvhRefraction->setText(QString::number(1.5));
	}
	if (renderer == "pssmlt") {
		mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->pssmlt);
        if (mainWindow->ui->pssmltSize->text() == "") mainWindow->ui->pssmltSize->setText(QString::number(512));
        if (mainWindow->ui->pssmltSamples->text() == "") mainWindow->ui->pssmltSamples->setText(QString::number(50));
        if (mainWindow->ui->pssmltRefraction->text() == "") mainWindow->ui->pssmltRefraction->setText(QString::number(1.5));
	}
	if (renderer == "smallmedia") {
		mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->smallmedia);
        if (mainWindow->ui->smallmediaSize->text() == "") mainWindow->ui->smallmediaSize->setText(QString::number(512));
        if (mainWindow->ui->smallmediaSamples->text() == "") mainWindow->ui->smallmediaSamples->setText(QString::number(50));
        if (mainWindow->ui->smallmediaRefraction->text() == "") mainWindow->ui->smallmediaRefraction->setText(QString::number(1.5));
	}
	if (renderer == "ppm") {
		mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->ppm);
        if (mainWindow->ui->ppmSize->text() == "") mainWindow->ui->ppmSize->setText(QString::number(512));
        if (mainWindow->ui->ppmSamples->text() == "") mainWindow->ui->ppmSamples->setText(QString::number(1000));
        if (mainWindow->ui->ppmRefraction->text() == "") mainWindow->ui->ppmRefraction->setText(QString::number(1.5));
	}
    if (renderer == "vrl") {
        mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->vrl);
        if (mainWindow->ui->vrlSize->text() == "") mainWindow->ui->vrlSize->setText(QString::number(512));
        if (mainWindow->ui->vrlSamples->text() == "") mainWindow->ui->vrlSamples->setText(QString::number(100));
        if (mainWindow->ui->vrlVRLPS->text() == "") mainWindow->ui->vrlVRLPS->setText(QString::number(10));
        if (mainWindow->ui->vrlBounces->text() == "") mainWindow->ui->vrlBounces->setText(QString::number(1));
        if (mainWindow->ui->vrlSigmaA->text() == "") mainWindow->ui->vrlSigmaA->setText(QString::number(.1));
        if (mainWindow->ui->vrlSigmaS->text() == "") mainWindow->ui->vrlSigmaS->setText(QString::number(.01));
        if (mainWindow->ui->vrlG->text() == "") mainWindow->ui->vrlG->setText(QString::number(0));
        if (mainWindow->ui->vrlRefraction->text() == "") mainWindow->ui->vrlRefraction->setText(QString::number(1.5));
        if (mainWindow->ui->vrlIntensity->text() == "") mainWindow->ui->vrlIntensity->setText(QString::number(50000));
    }
	if (renderer == "tests") {
		mainWindow->ui->renderModesSettings->setCurrentWidget(mainWindow->ui->tests);
	}
}

/**
 * QString to int with input control.
 */
int HelperFunctions::getTextAsInt(QString text) {
	int out;
	if (text == "") {
		return -1;
	} else {
		out = text.toInt();
		if (out == 0) {
			return -1;
		}
	}
	return out;
}

/**
 * QString to float with input control.
 */
float HelperFunctions::getTextAsFloat(QString text) {
	float out;
	if (text == "") {
		return -1;
	} else {
		out = text.replace(",", ".").toFloat();
		if (out == 0.0) {
			return -1;
		}
	}
	return out;
}

/**
 * Reads the input from the corresponding elements, assigns default values.
 */
void HelperFunctions::getInput(QString selectedRenderer, smallpaint::RenderInfo &info) {
    int size, spp, vrlps, bounces, scene, sampling, intensity;
    double refr, sigma_a, sigma_s, g;
    bool mediumRadiance, surfaceRadiance;

    if (selectedRenderer == "fixed") {
		spp = getTextAsInt(mainWindow->ui->fixedSamples->text());
		size = getTextAsInt(mainWindow->ui->fixedSize->text());
		refr = getTextAsFloat(mainWindow->ui->fixedRefraction->text());
	}

	if (selectedRenderer == "painterly") {
		spp = getTextAsInt(mainWindow->ui->painterlySamples->text());
		size = getTextAsInt(mainWindow->ui->painterlySize->text());
		refr = getTextAsFloat(mainWindow->ui->painterlyRefraction->text());
	}

	if (selectedRenderer == "bvh") {
		spp = getTextAsInt(mainWindow->ui->bvhSamples->text());
		size = getTextAsInt(mainWindow->ui->bvhSize->text());
		refr = getTextAsFloat(mainWindow->ui->bvhRefraction->text());
	}

	if (selectedRenderer == "pssmlt") {
		spp = getTextAsInt(mainWindow->ui->pssmltSamples->text());
		size = getTextAsInt(mainWindow->ui->pssmltSize->text());
		refr = getTextAsFloat(mainWindow->ui->pssmltRefraction->text());
	}

	if (selectedRenderer == "smallmedia") {
		spp = getTextAsInt(mainWindow->ui->smallmediaSamples->text());
		size = getTextAsInt(mainWindow->ui->smallmediaSize->text());
		refr = getTextAsFloat(mainWindow->ui->smallmediaRefraction->text());
	}

	if (selectedRenderer == "ppm") {
		spp = getTextAsInt(mainWindow->ui->ppmSamples->text());
		spp *= 1000;
		size = getTextAsInt(mainWindow->ui->ppmSize->text());
		refr = getTextAsFloat(mainWindow->ui->ppmRefraction->text());
	}

    if (selectedRenderer == "vrl") {
        spp = getTextAsInt(mainWindow->ui->vrlSamples->text());
        vrlps = getTextAsInt(mainWindow->ui->vrlVRLPS->text());
        size = getTextAsInt(mainWindow->ui->vrlSize->text());
        bounces = getTextAsInt(mainWindow->ui->vrlBounces->text());
        intensity = getTextAsInt(mainWindow->ui->vrlIntensity->text());
        scene = mainWindow->ui->vrlScene->currentIndex();
        sampling = mainWindow->ui->vrlSampling->currentIndex();
        refr = getTextAsFloat(mainWindow->ui->vrlRefraction->text());
        sigma_a = getTextAsFloat(mainWindow->ui->vrlSigmaA->text());
        sigma_s = getTextAsFloat(mainWindow->ui->vrlSigmaS->text());
        g = getTextAsFloat(mainWindow->ui->vrlG->text());
        mediumRadiance = mainWindow->ui->vrlMediumRadiance->isChecked();
        surfaceRadiance = mainWindow->ui->vrlSurfaceRadiance->isChecked();
    }


    if (spp == -1) spp = selectedRenderer == "ppm" ? 50000 : 50;
    if (spp < 1) spp = 1;
    info.spp = spp;

    if (vrlps == -1) vrlps = 10;
    if (vrlps < 1) vrlps = 1;
    info.vrlps = vrlps;

    if (size == -1) size = 512;
    size = qMin(2048, qMax(256, size));
    info.size = size;

    if (bounces == -1) bounces = 1;
    if (bounces < 1) bounces = 1;
    info.bounces = bounces;

    if (intensity == -1) intensity = 50000;
    if (intensity < 1) intensity = 1000;
    info.intensity = intensity;

    if (scene == -1) scene = 0;
    if (scene < 0 || scene > 5) scene = 0;
    info.scene = scene;

    if (sampling == -1) sampling = 0;
    if (sampling < 0 || sampling > 4) sampling = 0;
    info.sampling = sampling;

    if (refr == -1) refr = 1.5;
    refr = qMin(5.0, qMax(1.0, refr));
    info.refr = refr;

    if (sigma_a == -1) sigma_a = 0.1;
    sigma_a = qMin(100.0, qMax(0.0, sigma_a));
    info.sigma_a = sigma_a;

    if (sigma_s == -1) sigma_s = 0.01;
    sigma_s = qMin(100.0, qMax(0.0, sigma_s));
    info.sigma_s = sigma_s;

    if (g == -1) g = 0.0;
    g = qMin(1.0, qMax(-1.0, g));
    info.g = g;

    info.mediumRadiance = mediumRadiance;
    info.surfaceRadiance = surfaceRadiance;
}

/**
 * Intitializes the render information and sets some start up values.
 */
void HelperFunctions::initializeRenderInformation(QString selectedRenderer, smallpaint::RenderInfo info) {
	QString sppString;
	mainWindow->ui->renderButton->setText("Cancel");
    mainWindow->width = info.size;
    mainWindow->height = info.size;
    //mainWindow->ui->renderedImage->clear();
	mainWindow->lastImage = "";
    mainWindow->ui->progressBar->setMinimum(0);
    mainWindow->ui->progressBar->setMaximum(info.spp);
    sppString = QString::number(info.spp);
	mainWindow->ui->timeInfo->setText("Processing...");
	if (selectedRenderer != "ppm") {
        mainWindow->ui->renderInfo->setText("Rendering with smallpaint_" + selectedRenderer + ": " + QString::number(info.size) + "x"
                                            + QString::number(info.size) + " pixel, " + sppString + " samples");
	} else {
        mainWindow->ui->renderInfo->setText("Rendering with smallpaint_" + selectedRenderer + ": " + QString::number(info.size) + "x"
                                            + QString::number(info.size) + " pixel, " + sppString + " photons");
	}
}

/**
 * Adds leading zeros and processes time to DD:HH:MM:SS format.
 */
QString HelperFunctions::processTime(int secondsToProcess) {
	struct Padding {
		static QString process(int time) {
			if (time == 0) return "00";
			QString timeString = QString::number(time);
			if (time < 10) return "0" + timeString;
			return timeString;
		}
	};
	int days, hours, minutes, seconds;
	days = secondsToProcess / 60 / 60 / 24;
	hours = (secondsToProcess / 60 / 60) % 24;
	minutes = (secondsToProcess / 60) % 60;
	seconds = secondsToProcess % 60;
	return Padding::process(days) + ":" + Padding::process(hours) + ":" + Padding::process(minutes) + ":" + Padding::process(seconds);
}

/**
 * Updates the render information after every new image.
 */
void HelperFunctions::updateInfo(int currentSpp, int goalSpp) {
    mainWindow->ui->progressBar->setValue(currentSpp);

    QString out = "Percentage:\t" + QString::number((float)currentSpp/(float)goalSpp * 100.0f, 'f', 2) + "%\n";
    out += "Samples:\t" + QString::number(currentSpp) + " / " + QString::number(goalSpp) + "\n";
    int secondsElapsed = (clock() - mainWindow->start) / CLOCKS_PER_SEC;
    int secondsExpected = (goalSpp)*(secondsElapsed / (float)currentSpp);
    int secondsRemaining = secondsExpected - secondsElapsed;

    out += "Time elapsed:\t" + processTime(secondsElapsed) + "\n";
    out += "Time remaining:\t" + processTime(secondsRemaining) + "\n";
    out += "Expected Time:\t" + processTime(secondsExpected);
    mainWindow->ui->timeInfo->setText(out);
}
