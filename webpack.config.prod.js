var webpack = require('webpack');
var path = require("path");
var sharedConfig = require(path.resolve("./webpack.config.shared.js"));

module.exports = {
  context: __dirname,
  entry: sharedConfig.entry,
  output: sharedConfig.output,
  module: sharedConfig.module,
  sassLoader: sharedConfig.sassLoader,
  resolve: sharedConfig.resolve,

  plugins: [
    new webpack.DefinePlugin({
      'process.env': {
        'NODE_ENV': '"production"'
      }
    }),
    new webpack.optimize.UglifyJsPlugin({
      compress: {
        warnings: false
      }
    }),
    new webpack.optimize.OccurrenceOrderPlugin(),
    new webpack.optimize.DedupePlugin(),
    new webpack.optimize.CommonsChunkPlugin({
      name: 'common',
      minChunks: 2,
    }),
  ],
  devtool: 'source-map'
};
