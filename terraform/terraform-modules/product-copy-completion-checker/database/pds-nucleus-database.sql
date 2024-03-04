use pds_nucleus;

DROP TABLE IF EXISTS product_data_file_mapping;
CREATE TABLE product_data_file_mapping
(
    s3_url_of_product_label VARCHAR(1500),
    s3_url_of_data_file VARCHAR(1500),
    last_updated_epoch_time BIGINT,
    PRIMARY KEY (s3_url_of_product_label, s3_url_of_data_file)
);

DROP TABLE IF EXISTS data_file;
CREATE TABLE data_file
(
    s3_url_of_data_file VARCHAR(1500),
    last_updated_epoch_time BIGINT,
    PRIMARY KEY (s3_url_of_data_file)
);

DROP TABLE IF EXISTSproduct;
CREATE TABLE product
(
    s3_url_of_product_label VARCHAR(1500),
    processing_status VARCHAR(10),
    last_updated_epoch_time BIGINT,
    PRIMARY KEY (s3_url_of_product_label)
);
