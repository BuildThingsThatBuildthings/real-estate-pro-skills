import {Config} from '@remotion/cli/config';

// Block codec discipline from the proven pipeline: h264 yuv420p, CRF 18.
Config.setVideoImageFormat('jpeg');
Config.setPixelFormat('yuv420p');
Config.setCodec('h264');
Config.setCrf(18);
Config.setOverwriteOutput(true);
